import {useState} from "react"

export default function EmailsPanel({emails}){
  const [openIdx,setOpenIdx]=useState(null)
  if(!emails||emails.length===0) return null
  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4">
      <div className="text-xs text-gray-400 uppercase mb-3">Reporter emails</div>
      <ul className="space-y-2">
        {emails.map((e,i)=>(
          <li key={i} className="border border-gray-800 rounded">
            <button
              className="w-full text-left p-2 hover:bg-gray-800/40"
              onClick={()=>setOpenIdx(openIdx===i?null:i)}
            >
              <div className="flex items-center gap-3 text-sm">
                <span className="text-white">{e.student}</span>
                <span className="text-xs text-gray-400">{e.to||"(no email)"}</span>
                <span className="ml-auto text-[10px] px-2 py-0.5 rounded bg-gray-800 text-gray-300">{e.delivery?.mode||"?"}</span>
              </div>
              <div className="text-xs text-gray-400 truncate">{e.subject}</div>
            </button>
            {openIdx===i && (
              <pre className="p-3 border-t border-gray-800 bg-gray-950 text-xs text-gray-200 whitespace-pre-wrap font-sans">{e.body||""}</pre>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}


// helper notes:
// each email row collapses by default; click to read the full body. The pill on the
// right shows whether the email was actually sent ('sent') or just saved to disk
// ('dry_run') based on the EMAIL_DRY_RUN flag at run time.
