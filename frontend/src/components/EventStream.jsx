import {useEffect,useRef,useState} from "react"

const KIND_COLORS={
  phase:"text-amber-300",
  phase_step:"text-amber-200",
  agent_start:"text-cyan-300",
  agent_end:"text-cyan-200",
  agent_tool_call:"text-fuchsia-300",
  llm_call:"text-blue-300",
  llm_response:"text-blue-200",
  llm_usage:"text-emerald-400",
  llm_retry:"text-orange-400",
  tool_call_start:"text-violet-300",
  tool_call_end:"text-violet-200",
  run_created:"text-gray-400",
  submission_added:"text-gray-400",
  run_start_requested:"text-gray-400",
  run_error:"text-rose-400",
}

export default function EventStream({events}){
  const ref=useRef(null)
  const [expanded,setExpanded]=useState({})

  useEffect(()=>{
    if(ref.current){
      ref.current.scrollTop=ref.current.scrollHeight
    }
  },[events.length])

  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4">
      <div className="flex items-baseline justify-between mb-2">
        <div className="text-xs text-gray-400 uppercase">Live agent trace</div>
        <div className="text-xs text-gray-500">{events.length} events</div>
      </div>
      <div ref={ref} className="h-96 overflow-y-auto font-mono text-xs space-y-1">
        {events.map((e,i)=>{
          const cls=KIND_COLORS[e.kind]||"text-gray-300"
          const short=summarize(e)
          const isOpen=expanded[i]
          return (
            <div key={i} className="border-l-2 border-gray-800 pl-2">
              <button
                className="text-left w-full hover:bg-gray-800/40 rounded px-1 py-0.5"
                onClick={()=>setExpanded(s=>({...s,[i]:!s[i]}))}
              >
                <span className="text-gray-500">{(e.ts||"").slice(11,19)}</span>{" "}
                <span className={cls}>{e.kind}</span>{" "}
                <span className="text-gray-400">{short}</span>
              </button>
              {isOpen && (
                <pre className="mt-1 mb-2 p-2 bg-gray-950 border border-gray-800 rounded text-[10px] text-gray-300 whitespace-pre-wrap break-words">
                  {JSON.stringify(e.payload||{},null,2)}
                </pre>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function summarize(e){
  const p=e.payload||{}
  if(e.kind==="phase") return p.name||""
  if(e.kind==="phase_step") return `${p.agent||""} · ${p.action||""}${p.student?" · "+p.student:""}${p.final_total!==undefined?" · score "+p.final_total:""}`
  if(e.kind==="agent_tool_call") return `${p.agent||""} -> ${p.tool||""}`
  if(e.kind==="tool_call_start"||e.kind==="tool_call_end") return p.tool||""
  if(e.kind==="llm_call") return `${p.agent||""} (${p.model||""})`
  if(e.kind==="llm_usage") return `${p.agent||""} · in=${p.input_tokens||0} out=${p.output_tokens||0}`
  if(e.kind==="llm_response") return (p.preview||"").slice(0,80)
  if(e.kind==="llm_retry") return `${p.agent} attempt ${p.attempt} (code ${p.code})`
  if(e.kind==="submission_added") return p.student||""
  return Object.keys(p).slice(0,3).map(k=>`${k}=${String(p[k]).slice(0,40)}`).join(" ")
}


// helper notes:
// KIND_COLORS  -> tiny lookup that gives each event kind its own color so the live
//                 trace is easy to scan visually.
// EventStream  -> auto-scrolls to the bottom as new events arrive. Click any row to
//                 expand the full JSON payload (pretty-printed) - this is the
//                 "expandable agent trace" the proposal asks for.
// summarize()  -> one-line summary line per event kind, so a closed row is still
//                 readable without unfolding the payload.
