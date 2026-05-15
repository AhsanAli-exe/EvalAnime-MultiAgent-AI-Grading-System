import {useEffect,useRef,useState} from "react"
import {getRunDetail,getRunSummary,startRun,approveRun,openRunSocket} from "../api"
import PhaseTracker from "./PhaseTracker"
import EventStream from "./EventStream"
import ResultsTable from "./ResultsTable"
import SimilarityPanel from "./SimilarityPanel"
import EmailsPanel from "./EmailsPanel"
import RubricPanel from "./RubricPanel"
import ReviewPanel from "./ReviewPanel"

const PHASES=["INSPECT","DESIGN_RUBRIC","GRADE_EACH","DETECT_PLAGIARISM","GOVERNANCE","AWAITING_APPROVAL","REPORT"]

export default function Dashboard({runId}){
  const [detail,setDetail]=useState(null)
  const [summary,setSummary]=useState(null)
  const [events,setEvents]=useState([])
  const [tokenTotals,setTokenTotals]=useState({input:0,output:0})
  const wsRef=useRef(null)

  async function refresh(){
    try{
      const d=await getRunDetail(runId)
      setDetail(d)
      const s=await getRunSummary(runId)
      setSummary(s?.summary||null)
    }catch{}
  }

  useEffect(()=>{
    setEvents([])
    setTokenTotals({input:0,output:0})
    refresh()
    if(wsRef.current){try{wsRef.current.close()}catch{}}
    const ws=openRunSocket(runId,(ev)=>{
      if(ev.kind==="ping") return
      setEvents(prev=>[...prev,ev])
      if(ev.kind==="llm_usage"){
        const p=ev.payload||{}
        setTokenTotals(t=>({input:t.input+(p.input_tokens||0),output:t.output+(p.output_tokens||0)}))
      }
      if(ev.kind==="phase" && ["DONE","REPORT","AWAITING_APPROVAL"].includes(ev.payload?.name)){
        setTimeout(refresh,300)
      }
      if(ev.kind==="phase_step"&&ev.payload?.action==="end"){
        setTimeout(refresh,200)
      }
      if(ev.kind==="result_edited"||ev.kind==="run_approved"){
        setTimeout(refresh,200)
      }
    })
    wsRef.current=ws
    return ()=>{try{ws.close()}catch{}}
  // eslint-disable-next-line
  },[runId])

  const run=detail?.run
  const phases=PHASES.map(name=>{
    const start=events.find(e=>e.kind==="phase"&&e.payload?.name===name)
    const next=events.find(e=>e.kind==="phase"&&PHASES.indexOf(e.payload?.name)>PHASES.indexOf(name))
    const done=events.find(e=>e.kind==="phase"&&e.payload?.name==="DONE")
    const status=done||next?"done":start?"running":"pending"
    return {name,status}
  })

  return (
    <div className="space-y-6">
      <div className="flex items-baseline gap-4">
        <h2 className="text-xl font-semibold text-white">Run <span className="font-mono">{runId}</span></h2>
        <div className="text-xs text-gray-400">{run?.assignment_name}</div>
        <StatusBadge status={run?.status}/>
        <div className="ml-auto text-xs text-gray-400">tokens · in {tokenTotals.input} / out {tokenTotals.output}</div>
        {run?.status==="created" && (
          <button
            onClick={async()=>{await startRun(runId);refresh()}}
            className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 rounded text-white text-xs"
          >Start agent team</button>
        )}
        {run?.status==="awaiting_approval" && (
          <button
            onClick={async()=>{await approveRun(runId);refresh()}}
            className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 rounded text-white text-xs"
          >Approve &amp; send emails</button>
        )}
      </div>

      <PhaseTracker phases={phases}/>

      {run?.status==="awaiting_approval" && (
        <div className="bg-amber-900/40 border border-amber-700 rounded p-3 text-sm text-amber-100">
          Grading is complete. Review the results below; click <b>Edit</b> on any row to override a score
          or feedback. When you are happy, click <b>Approve &amp; send emails</b> at the top right to
          dispatch the reporter agent.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ResultsTable detail={detail} onChanged={refresh}/>
        <EventStream events={events}/>
      </div>

      <ReviewPanel governance={summary?.governance}/>
      <RubricPanel rubric={summary?.rubric}/>
      <SimilarityPanel plagiarism={summary?.plagiarism}/>
      <EmailsPanel emails={summary?.emails}/>
    </div>
  )
}


function StatusBadge({status}){
  if(!status) return null
  const map={
    created:"bg-gray-700 text-gray-200",
    running:"bg-amber-700 text-amber-100",
    awaiting_approval:"bg-amber-600 text-amber-50",
    running_emails:"bg-cyan-700 text-cyan-100",
    completed:"bg-emerald-700 text-emerald-100",
  }
  return <span className={"inline-block px-2 py-0.5 rounded text-[10px] uppercase "+(map[status]||"bg-gray-700 text-gray-200")}>{status.replace(/_/g," ")}</span>
}


// helper notes:
// PHASES         -> the high-level phases shown in the tracker, including the new
//                   AWAITING_APPROVAL state between GOVERNANCE and REPORT.
// refresh()      -> pulls /runs/:id (results) and /runs/:id/summary (final summary.json).
//                   Called on mount, on certain ws events, and after any phase_end.
// useEffect()    -> opens the websocket on runId change; appends every event into
//                   `events`. Live token totals are added up from llm_usage events
//                   so the user sees spend going up in real time.
// phases         -> derived from `events`: a phase is 'running' once its 'phase' event
//                   appears and 'done' once a later phase event (or DONE) is seen.
