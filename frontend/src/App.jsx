import {useEffect,useState} from "react"
import {getHealth,listRuns,deleteRun} from "./api"
import UploadForm from "./components/UploadForm"
import Dashboard from "./components/Dashboard"
import "./App.css"

function App(){
  const [health,setHealth]=useState(null)
  const [runs,setRuns]=useState([])
  const [selectedRunId,setSelectedRunId]=useState(null)

  async function refreshRuns(){
    try{
      const list=await listRuns()
      setRuns(list)
    }catch{}
  }

  useEffect(()=>{
    getHealth().then(setHealth).catch(()=>setHealth({ok:false}))
    refreshRuns()
    const t=setInterval(refreshRuns,4000)
    return ()=>clearInterval(t)
  },[])

  return (
    <div className="min-h-screen flex flex-col">
      <header className="px-6 py-3 border-b border-gray-800 flex items-center gap-4 bg-gray-900">
        <h1 className="text-xl font-semibold text-white">Evalanime</h1>
        <span className="text-xs text-gray-400">AI Teaching Assistant</span>
        <div className="ml-auto text-xs">
          {health?.ok
            ? <span className="text-emerald-400">backend up · gemini {health.gemini_key_loaded?"key loaded":"no key"}</span>
            : <span className="text-rose-400">backend not reachable</span>}
        </div>
      </header>

      <div className="flex-1 flex">
        <aside className="w-64 border-r border-gray-800 p-3 overflow-y-auto">
          <button
            className="w-full mb-3 px-3 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium"
            onClick={()=>setSelectedRunId(null)}
          >+ New run</button>
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-2 px-1">Recent runs</div>
          <ul className="space-y-1">
            {runs.map(r=>(
              <li key={r.id} className={"group relative rounded "+(selectedRunId===r.id?"bg-gray-800":"hover:bg-gray-800/60")}>
                <button
                  className="w-full text-left pr-7 px-2 py-2 text-sm"
                  onClick={()=>setSelectedRunId(r.id)}
                >
                  <div className="font-mono text-xs text-gray-400">{r.id}</div>
                  <div className="truncate text-white">{r.assignment_name}</div>
                  <div className="text-xs"><StatusPill s={r.status}/></div>
                </button>
                <button
                  type="button"
                  title="Delete run"
                  className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-rose-300 text-xs px-1 py-0.5 rounded hover:bg-gray-900"
                  onClick={async(e)=>{
                    e.stopPropagation()
                    const busy=r.status==="running"||r.status==="running_emails"
                    if(busy){alert(`Cannot delete while status is "${r.status}"`); return}
                    if(!confirm(`Delete run ${r.id}? This removes the run, its events, results and uploaded files. Cannot be undone.`)) return
                    try{
                      await deleteRun(r.id)
                      if(selectedRunId===r.id) setSelectedRunId(null)
                      refreshRuns()
                    }catch(err){alert(String(err.message||err))}
                  }}
                >🗑</button>
              </li>
            ))}
            {runs.length===0 && <li className="text-xs text-gray-500 px-1">no runs yet</li>}
          </ul>
        </aside>

        <main className="flex-1 p-6 overflow-y-auto">
          {selectedRunId
            ? <Dashboard runId={selectedRunId}/>
            : <UploadForm onCreated={(id)=>{refreshRuns();setSelectedRunId(id)}}/>}
        </main>
      </div>
    </div>
  )
}

function StatusPill({s}){
  const map={
    created:"bg-gray-700 text-gray-200",
    running:"bg-amber-700 text-amber-100",
    awaiting_approval:"bg-amber-600 text-amber-50",
    running_emails:"bg-cyan-700 text-cyan-100",
    completed:"bg-emerald-700 text-emerald-100",
  }
  return <span className={"inline-block px-2 py-0.5 rounded text-[10px] mt-1 "+(map[s]||"bg-gray-700 text-gray-200")}>{(s||"?").replace(/_/g," ")}</span>
}

export default App
