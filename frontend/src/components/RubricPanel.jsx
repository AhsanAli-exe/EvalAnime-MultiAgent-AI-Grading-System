export default function RubricPanel({rubric}){
  if(!rubric||!(rubric.criteria||[]).length) return null
  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-xs text-gray-400 uppercase">Rubric</div>
        <div className="text-xs text-gray-500">total {rubric.max_total||0}</div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {rubric.criteria.map((c,i)=>(
          <div key={i} className="border border-gray-800 rounded p-3">
            <div className="flex items-baseline justify-between">
              <div className="text-white font-medium">{c.q_id||`Criterion ${i+1}`}</div>
              <div className="text-xs text-gray-400">max {c.max}</div>
            </div>
            <ul className="mt-2 space-y-1 text-xs">
              {(c.levels||[]).map((l,j)=>(
                <li key={j} className="flex gap-2">
                  <span className="text-gray-400 w-16">{l.label}</span>
                  <span className="text-gray-500 w-12">≥{Math.round((l.min_pct||0)*100)}%</span>
                  <span className="text-gray-300">{l.desc}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}


// helper notes:
// shows the rubric the Rubric Designer (Pro) produced. One card per criterion with
// its level descriptors (excellent/good/weak/poor) and required minimum percentage.
