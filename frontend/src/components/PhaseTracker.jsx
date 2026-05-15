export default function PhaseTracker({phases}){
  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4">
      <div className="text-xs text-gray-400 uppercase mb-3">Pipeline</div>
      <ol className="flex flex-wrap gap-2">
        {phases.map((p,i)=>(
          <li key={p.name} className="flex items-center gap-2">
            <span className={
              "px-3 py-1 rounded text-xs font-medium "+
              (p.status==="done"?"bg-emerald-700 text-emerald-100":
               p.status==="running"?"bg-amber-600 text-amber-50 animate-pulse":
               "bg-gray-800 text-gray-500")
            }>
              {i+1}. {p.name}
            </span>
            {i<phases.length-1 && <span className="text-gray-700">→</span>}
          </li>
        ))}
      </ol>
    </div>
  )
}


// helper notes:
// PhaseTracker -> renders the 5 phases (INSPECT, DESIGN_RUBRIC, GRADE_EACH,
//                 DETECT_PLAGIARISM, REPORT) as colored chips. Color tells status:
//                 grey=pending, amber+pulse=running, green=done. Status is derived
//                 in Dashboard.jsx from the live events stream.
