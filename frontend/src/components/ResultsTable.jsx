import {useState,useEffect} from "react"
import {patchResult} from "../api"

export default function ResultsTable({detail,onChanged}){
  const submissions=detail?.submissions||[]
  const results=detail?.results||[]
  const status=detail?.run?.status
  const bySubId=Object.fromEntries(results.map(r=>[r.submission_id,r]))
  const editable=status==="awaiting_approval"
  const runId=detail?.run?.id

  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4">
      <div className="flex items-baseline gap-3 mb-3">
        <div className="text-xs text-gray-400 uppercase">Per-student results</div>
        {editable && <span className="text-[10px] uppercase px-2 py-0.5 rounded bg-amber-700 text-amber-100">awaiting approval · edits allowed</span>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-xs text-gray-400 uppercase">
            <tr>
              <th className="text-left p-1">Student</th>
              <th className="text-left p-1">File</th>
              <th className="text-right p-1">Score</th>
              <th className="text-left p-1">Feedback</th>
              <th className="text-left p-1">Deductions</th>
              {editable && <th className="text-right p-1"></th>}
            </tr>
          </thead>
          <tbody>
            {submissions.map(s=>{
              const r=bySubId[s.id]
              return (
                <ResultRow
                  key={s.id}
                  runId={runId}
                  submission={s}
                  result={r}
                  editable={editable}
                  onChanged={onChanged}
                />
              )
            })}
            {submissions.length===0 && (
              <tr><td colSpan={editable?6:5} className="p-2 text-gray-500 text-center">no submissions yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const FEEDBACK_MAX=4000

function ResultRow({runId,submission,result,editable,onChanged}){
  const [editing,setEditing]=useState(false)
  const [score,setScore]=useState(result?.score??0)
  const [feedback,setFeedback]=useState(result?.feedback||"")
  const [saving,setSaving]=useState(false)
  const [err,setErr]=useState("")

  const maxScore=Number(result?.max_score||30)

  useEffect(()=>{
    if(!editing){
      setScore(result?.score??0)
      setFeedback(result?.feedback||"")
      setErr("")
    }
  },[result,editing])

  function localValidate(){
    const n=Number(score)
    if(!Number.isFinite(n)) return "score must be a number"
    if(n<0) return "score cannot be negative"
    if(n>maxScore) return `score cannot exceed ${maxScore}`
    if(feedback && feedback.length>FEEDBACK_MAX) return `feedback too long (${feedback.length}/${FEEDBACK_MAX})`
    return ""
  }

  async function save(){
    const v=localValidate()
    if(v){setErr(v);return}
    setSaving(true)
    setErr("")
    try{
      await patchResult(runId,submission.id,{score:Number(score),feedback})
      setEditing(false)
      onChanged&&onChanged()
    }catch(e){
      setErr(String(e.message||e))
    }finally{
      setSaving(false)
    }
  }

  const liveErr=editing?localValidate():""

  if(editing){
    const hasErr=Boolean(liveErr||err)
    return (
      <tr className="border-t border-gray-800 bg-gray-950">
        <td className="p-1 text-white align-top">{submission.student_name}</td>
        <td className="p-1 text-gray-400 font-mono text-xs align-top">{submission.file_name}</td>
        <td className="p-1 align-top">
          <input
            type="number" min={0} max={maxScore} step={1}
            value={score} onChange={e=>setScore(e.target.value)}
            className={"w-16 bg-gray-800 border rounded px-2 py-1 text-right text-sm "+(hasErr?"border-rose-500":"border-gray-700")}
          />
          <span className="text-xs text-gray-500"> / {maxScore}</span>
        </td>
        <td className="p-1 align-top" colSpan={2}>
          <textarea
            rows={3}
            value={feedback} onChange={e=>setFeedback(e.target.value)}
            maxLength={FEEDBACK_MAX}
            className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs"
          />
          <div className="flex items-baseline justify-between mt-1">
            <span className={"text-xs "+(hasErr?"text-rose-400":"text-gray-500")}>
              {liveErr||err||" "}
            </span>
            <span className="text-[10px] text-gray-500">{feedback.length}/{FEEDBACK_MAX}</span>
          </div>
        </td>
        <td className="p-1 align-top text-right">
          <div className="flex flex-col gap-1">
            <button type="button" disabled={saving||Boolean(liveErr)} onClick={save}
              className="px-2 py-0.5 bg-emerald-600 hover:bg-emerald-500 rounded text-xs text-white disabled:bg-gray-700 disabled:cursor-not-allowed">
              {saving?"…":"Save"}
            </button>
            <button type="button" onClick={()=>setEditing(false)}
              className="px-2 py-0.5 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-200">Cancel</button>
          </div>
        </td>
      </tr>
    )
  }

  return (
    <tr className="border-t border-gray-800">
      <td className="p-1 text-white align-top">{submission.student_name}</td>
      <td className="p-1 text-gray-400 font-mono text-xs align-top">{submission.file_name}</td>
      <td className="p-1 text-right align-top">
        {result ? <span className="text-emerald-300">{result.score}/{result.max_score}</span> : <span className="text-gray-500">…</span>}
      </td>
      <td className="p-1 text-xs text-gray-300 align-top max-w-md">
        {result?.feedback ? <div className="line-clamp-3">{result.feedback}</div> : <span className="text-gray-600">—</span>}
      </td>
      <td className="p-1 text-xs text-rose-300 align-top">
        {(result?.breakdown?.deductions||[]).map((d,i)=>(
          <div key={i}>−{d.points} {d.reason}</div>
        ))}
      </td>
      {editable && (
        <td className="p-1 align-top text-right">
          <button type="button" onClick={()=>setEditing(true)}
            className="px-2 py-0.5 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-200" disabled={!result}>Edit</button>
        </td>
      )}
    </tr>
  )
}


// helper notes:
// editable    -> only true when run.status === 'awaiting_approval' (after grading,
//                before emails). At any other time the Edit column is hidden.
// ResultRow   -> in view mode shows score / feedback preview / deductions; clicking
//                Edit flips to a row with a number input + textarea + Save / Cancel.
//                Save calls PATCH /runs/:id/results/:sub_id and then onChanged()
//                tells the Dashboard to re-fetch results.
