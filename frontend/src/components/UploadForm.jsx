import {useState} from "react"
import {createRun,startRun} from "../api"

const DEFAULTS={cosine:0.7,jaccard:0.2,minConf:0.75}
const MAX_TOTAL_MIN=1
const MAX_TOTAL_MAX=200

export default function UploadForm({onCreated}){
  const [assignment,setAssignment]=useState(null)
  const [submissions,setSubmissions]=useState([])
  const [students,setStudents]=useState([])
  const [rubricFile,setRubricFile]=useState(null)
  const [maxTotal,setMaxTotal]=useState(30)
  const [thresholds,setThresholds]=useState(DEFAULTS)
  const [autoApprove,setAutoApprove]=useState(false)
  const [autoStart,setAutoStart]=useState(true)
  const [showAdvanced,setShowAdvanced]=useState(false)
  const [busy,setBusy]=useState(false)
  const [err,setErr]=useState("")

  function onSubmissionsPick(files){
    const arr=Array.from(files||[])
    setSubmissions(arr)
    setStudents(arr.map((f,i)=>({name:students[i]?.name||`Student ${i+1}`,email:students[i]?.email||""})))
  }

  function updateStudent(i,key,value){
    const next=[...students]
    next[i]={...next[i],[key]:value}
    setStudents(next)
  }

  function validate(){
    if(!assignment) return "pick an assignment file"
    if(submissions.length===0) return "pick at least one submission"
    const mt=Number(maxTotal)
    if(!Number.isFinite(mt)||mt<MAX_TOTAL_MIN||mt>MAX_TOTAL_MAX){
      return `total marks must be between ${MAX_TOTAL_MIN} and ${MAX_TOTAL_MAX}`
    }
    return ""
  }

  async function submit(e){
    e.preventDefault()
    const v=validate()
    if(v){setErr(v);return}
    setErr("")
    setBusy(true)
    try{
      const out=await createRun({
        assignment,
        submissions,
        names:students.map(s=>s.name),
        emails:students.map(s=>s.email),
        rubricFile,
        maxTotal:Math.round(Number(maxTotal)),
        thresholds,
        autoApprove,
      })
      if(autoStart) await startRun(out.run_id)
      onCreated&&onCreated(out.run_id)
    }catch(e){
      setErr(String(e.message||e))
    }finally{
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="max-w-3xl mx-auto space-y-6">
      <h2 className="text-2xl font-semibold text-white">New grading run</h2>

      <div className="bg-gray-900 border border-gray-800 rounded p-4 space-y-3">
        <label className="block text-sm text-gray-300">Assignment file (PDF)</label>
        <input
          type="file"
          accept=".pdf"
          onChange={(e)=>setAssignment(e.target.files?.[0]||null)}
          className="text-sm text-gray-200"
        />
        {assignment && <div className="text-xs text-gray-400">{assignment.name} · {(assignment.size/1024).toFixed(1)} KB</div>}

        <div className="pt-3 border-t border-gray-800">
          <label className="block text-sm text-gray-300 mb-1">Total marks</label>
          <div className="flex items-center gap-3">
            <input
              type="number"
              min={MAX_TOTAL_MIN}
              max={MAX_TOTAL_MAX}
              step={1}
              value={maxTotal}
              onChange={(e)=>setMaxTotal(e.target.value)}
              className="w-24 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-right"
            />
            <span className="text-xs text-gray-500">how many marks is the whole assignment out of (1–{MAX_TOTAL_MAX})</span>
          </div>
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded p-4 space-y-3">
        <label className="block text-sm text-gray-300">Student submissions (pdf / docx / zip / image-pdf)</label>
        <input
          type="file"
          multiple
          accept=".pdf,.docx,.zip"
          onChange={(e)=>onSubmissionsPick(e.target.files)}
          className="text-sm text-gray-200"
        />
        {submissions.length>0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-gray-400 uppercase">
                <tr><th className="text-left p-1">File</th><th className="text-left p-1">Student name</th><th className="text-left p-1">Email</th></tr>
              </thead>
              <tbody>
                {submissions.map((f,i)=>(
                  <tr key={i} className="border-t border-gray-800">
                    <td className="p-1 text-gray-300 font-mono text-xs">{f.name}</td>
                    <td className="p-1">
                      <input
                        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm"
                        value={students[i]?.name||""}
                        onChange={(e)=>updateStudent(i,"name",e.target.value)}
                      />
                    </td>
                    <td className="p-1">
                      <input
                        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm"
                        placeholder="optional"
                        value={students[i]?.email||""}
                        onChange={(e)=>updateStudent(i,"email",e.target.value)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={()=>setShowAdvanced(s=>!s)}
        className="text-sm text-emerald-300 hover:text-emerald-200"
      >{showAdvanced?"− Hide":"+ Show"} advanced (rubric upload, thresholds)</button>

      {showAdvanced && (
        <div className="space-y-4">
          <div className="bg-gray-900 border border-gray-800 rounded p-4 space-y-3">
            <label className="block text-sm text-gray-300">Custom rubric (optional, JSON)</label>
            <p className="text-xs text-gray-500">If provided, the Rubric Designer agent will be skipped and your rubric will be used as-is.</p>
            <input
              type="file"
              accept="application/json,.json"
              onChange={(e)=>setRubricFile(e.target.files?.[0]||null)}
              className="text-sm text-gray-200"
            />
            {rubricFile && <div className="text-xs text-gray-400">{rubricFile.name}</div>}
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded p-4 space-y-4">
            <div className="text-sm text-gray-300">Similarity thresholds</div>
            <Slider label="Cosine ≥" value={thresholds.cosine} step={0.05} min={0.2} max={0.95}
              onChange={(v)=>setThresholds(t=>({...t,cosine:v}))}
              hint="text-similarity floor before a pair is even shown as suspicious"/>
            <Slider label="Jaccard ≥" value={thresholds.jaccard} step={0.05} min={0.05} max={0.6}
              onChange={(v)=>setThresholds(t=>({...t,jaccard:v}))}
              hint="phrase-overlap floor (5-gram). Catches copy-paste even if reworded slightly"/>
            <Slider label="Min LLM confidence" value={thresholds.minConf} step={0.05} min={0.5} max={0.99}
              onChange={(v)=>setThresholds(t=>({...t,minConf:v}))}
              hint="below this, plagiarism verdicts go to human review instead of accusation"/>
            <button
              type="button"
              onClick={()=>setThresholds(DEFAULTS)}
              className="text-xs text-gray-400 hover:text-gray-200"
            >reset to defaults</button>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-4">
        <label className="text-sm text-gray-300 flex items-center gap-2">
          <input type="checkbox" checked={autoStart} onChange={(e)=>setAutoStart(e.target.checked)}/>
          Auto-start grading after upload
        </label>
        <label className="text-sm text-gray-300 flex items-center gap-2">
          <input type="checkbox" checked={autoApprove} onChange={(e)=>setAutoApprove(e.target.checked)}/>
          Auto-send emails (skip teacher review)
        </label>
        <button
          type="submit"
          disabled={busy}
          className="ml-auto px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 rounded text-white text-sm font-medium"
        >{busy?"Uploading…":"Create run"}</button>
      </div>

      {err && <div className="text-rose-400 text-sm">{err}</div>}
    </form>
  )
}

function Slider({label,value,onChange,min,max,step,hint}){
  return (
    <div>
      <div className="flex items-baseline gap-3 mb-1">
        <span className="text-sm text-gray-300">{label}</span>
        <span className="font-mono text-emerald-300 text-sm">{Number(value).toFixed(2)}</span>
        {hint && <span className="text-xs text-gray-500">{hint}</span>}
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={(e)=>onChange(parseFloat(e.target.value))}
        className="w-full accent-emerald-500"
      />
    </div>
  )
}


// helper notes:
// DEFAULTS         -> the same defaults the backend uses if no overrides are sent.
// rubricFile       -> optional. If set, backend skips the Rubric Designer agent.
// thresholds       -> three knobs the teacher controls. Sent as form fields on
//                     create_run; the run's config.json holds them; team.py reads
//                     them at run time.
// autoApprove      -> if checked, grading runs straight into REPORT (emails). If
//                     unchecked (default) the run stops at 'awaiting_approval' so
//                     the teacher can review/edit grades first.
// Slider           -> tiny labeled range input. accent-emerald-500 colors the thumb.
