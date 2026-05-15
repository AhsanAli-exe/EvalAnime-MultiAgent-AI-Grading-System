import {useState} from "react"

const SEVERITY_COLORS={
  high:"bg-rose-700 text-rose-100",
  medium:"bg-amber-700 text-amber-100",
  low:"bg-gray-700 text-gray-200",
}

export default function ReviewPanel({governance}){
  const [showPolicy,setShowPolicy]=useState(false)
  if(!governance) return null
  const items=governance.review_items||[]
  const principles=governance.principles||[]
  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4">
      <div className="flex items-baseline gap-3 mb-3">
        <div className="text-xs text-gray-400 uppercase">Governance · human review queue</div>
        <div className="text-xs text-gray-500">{items.length} item(s) flagged</div>
        <button
          className="ml-auto text-xs text-emerald-300 hover:text-emerald-200"
          onClick={()=>setShowPolicy(s=>!s)}
        >{showPolicy?"hide":"show"} policy & principles</button>
      </div>

      {items.length===0 && <div className="text-xs text-emerald-400">no items need human review · all decisions met confidence thresholds</div>}
      <ul className="space-y-2">
        {items.map((it,i)=>(
          <li key={i} className="border border-gray-800 rounded p-2 text-sm flex items-center gap-3 bg-gray-950">
            <span className={"text-[10px] uppercase px-2 py-0.5 rounded "+(SEVERITY_COLORS[it.severity]||SEVERITY_COLORS.low)}>{it.severity||"low"}</span>
            <span className="text-white font-mono text-xs">{it.kind}</span>
            <span className="text-gray-400 text-xs">{it.student||(it.pair?it.pair.join(" ↔ "):"")}</span>
            <span className="text-gray-300 text-xs ml-auto">{it.reason}</span>
          </li>
        ))}
      </ul>

      {showPolicy && (
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-gray-400 uppercase mb-2">Policy thresholds</div>
            <pre className="text-[11px] text-gray-300 bg-gray-950 border border-gray-800 rounded p-2 overflow-x-auto">{JSON.stringify(governance.policy||{},null,2)}</pre>
          </div>
          <div>
            <div className="text-xs text-gray-400 uppercase mb-2">Ethics principles</div>
            <ul className="text-xs text-gray-300 space-y-1 list-disc pl-4">
              {principles.map((p,i)=><li key={i}>{p}</li>)}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}


// helper notes:
// SEVERITY_COLORS  -> color pill for each severity level (high/medium/low).
// ReviewPanel      -> shows what the governance module decided to escalate to a
//                     human. Empty list = all decisions met the policy thresholds.
//                     The "show policy & principles" toggle reveals the rule book
//                     and the human-readable ethics statement, both pulled from
//                     backend/governance.py at run time.
