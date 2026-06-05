import {useState} from "react"

const MODE_STYLES={
  sent:"bg-emerald-700 text-emerald-50",
  dry_run:"bg-amber-700 text-amber-100",
  failed:"bg-rose-700 text-rose-100",
}

export default function EmailsPanel({emails}){
  const [openIdx,setOpenIdx]=useState(null)
  if(!emails||emails.length===0) return null

  const counts={sent:0,dry_run:0,failed:0,other:0}
  for(const e of emails){
    const m=e.delivery?.mode||"other"
    if(counts[m]!==undefined) counts[m]++; else counts.other++
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4">
      <div className="flex items-baseline gap-3 mb-3">
        <div className="text-xs text-gray-400 uppercase">Reporter emails</div>
        <div className="flex gap-3 text-xs">
          {counts.sent>0 && <span className="text-emerald-300"><b>{counts.sent}</b> sent</span>}
          {counts.dry_run>0 && <span className="text-amber-300"><b>{counts.dry_run}</b> saved (no email)</span>}
          {counts.failed>0 && <span className="text-rose-400"><b>{counts.failed}</b> failed</span>}
        </div>
      </div>
      <ul className="space-y-2">
        {emails.map((e,i)=>{
          const mode=e.delivery?.mode||"?"
          const style=MODE_STYLES[mode]||"bg-gray-800 text-gray-300"
          return (
            <li key={i} className="border border-gray-800 rounded">
              <button
                className="w-full text-left p-2 hover:bg-gray-800/40"
                onClick={()=>setOpenIdx(openIdx===i?null:i)}
              >
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-white">{e.student}</span>
                  {e.to
                    ? <span className="text-xs text-gray-400">{e.to}</span>
                    : <span className="text-xs text-amber-300 italic">no email provided</span>}
                  <span className={"ml-auto text-[10px] uppercase px-2 py-0.5 rounded "+style}>{mode.replace("_"," ")}</span>
                </div>
                <div className="text-xs text-gray-400 truncate">{e.subject}</div>
                {e.delivery?.error && <div className="text-xs text-rose-400 mt-1">{String(e.delivery.error).slice(0,140)}</div>}
              </button>
              {openIdx===i && (
                <pre className="p-3 border-t border-gray-800 bg-gray-950 text-xs text-gray-200 whitespace-pre-wrap font-sans">{e.body||""}</pre>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}


// helper notes:
// MODE_STYLES   -> pill color for each delivery mode (sent / dry_run / failed).
// counts        -> shown in the header so the teacher can see at a glance how many
//                  emails really went out vs how many were skipped because no
//                  address was provided.
// row body      -> shows recipient (or an amber "no email provided" note), subject,
//                  and a clickable expand for the full email body. If sending failed,
//                  the SMTP error is shown inline so the teacher can debug.
