export default function SimilarityPanel({plagiarism}){
  if(!plagiarism) return null
  const ids=plagiarism.matrix_ids||[]
  const cos=plagiarism.cosine||[]
  const flags=plagiarism.flags||[]
  const judgments=plagiarism.judgments||[]

  const flagKey=(a,b)=>[a,b].sort().join("|")
  const flagSet=new Set(flags.map(f=>flagKey(f.a,f.b)))

  function heat(v){
    if(v>=0.7) return "bg-rose-700 text-rose-50"
    if(v>=0.5) return "bg-orange-700 text-orange-50"
    if(v>=0.3) return "bg-amber-700 text-amber-100"
    return "bg-gray-800 text-gray-400"
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4">
      <div className="text-xs text-gray-400 uppercase mb-3">Similarity & plagiarism</div>

      {ids.length>0 && (
        <div className="overflow-x-auto mb-4">
          <table className="text-xs border-collapse">
            <thead>
              <tr>
                <th className="p-1"></th>
                {ids.map(id=><th key={id} className="p-1 text-gray-400 font-normal text-[10px]">{id.split(" ")[0]}</th>)}
              </tr>
            </thead>
            <tbody>
              {ids.map((rowId,i)=>(
                <tr key={rowId}>
                  <td className="p-1 text-gray-400 text-[10px] text-right">{rowId.split(" ")[0]}</td>
                  {ids.map((colId,j)=>{
                    const v=cos[i]?.[j]||0
                    const isFlag=i!==j && flagSet.has(flagKey(rowId,colId))
                    return (
                      <td key={colId} className="p-1">
                        <div className={"w-12 h-7 rounded flex items-center justify-center "+heat(v)+(isFlag?" ring-2 ring-rose-400":"")}>{v.toFixed(2)}</div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="space-y-2">
        <div className="text-xs text-gray-400">Investigator judgments</div>
        {judgments.length===0 && <div className="text-xs text-gray-500">no pairs flagged</div>}
        {judgments.map((j,i)=>(
          <div key={i} className="text-sm border border-gray-800 rounded p-2 bg-gray-950">
            <div className="flex items-center gap-2">
              <span className="text-white">{j.a} ↔ {j.b}</span>
              <span className={
                "text-[10px] uppercase px-2 py-0.5 rounded "+
                (j.verdict==="plagiarized"?"bg-rose-700 text-rose-100":
                 j.verdict==="paraphrased"?"bg-orange-700 text-orange-100":
                 j.verdict==="coincidental"?"bg-emerald-700 text-emerald-100":
                 "bg-gray-700 text-gray-200")
              }>{j.verdict}</span>
              <span className="text-xs text-gray-400">conf {Math.round((j.confidence||0)*100)}%</span>
              <span className="ml-auto text-xs text-gray-500">cos {j.cosine} · jac {j.jaccard}</span>
            </div>
            <div className="text-xs text-gray-400 mt-1">{j.reason}</div>
          </div>
        ))}
      </div>
    </div>
  )
}


// helper notes:
// heat(v)    -> turns a cosine value into a tailwind background color: deep red when
//               >=0.7 (very suspicious), through amber, down to grey for low overlap.
// flagSet    -> the set of pairs the deterministic similarity tool flagged as evidence.
//               These get a ring outline in the matrix so the eye finds them fast.
// judgments  -> one card per flagged pair with the LLM's verdict + reasoning.
//               This is where you can SEE the "evidence -> LLM judgment" two-layer
//               design from the proposal.
