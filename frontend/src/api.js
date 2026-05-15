export async function getHealth(){
  const r=await fetch("/health")
  return r.json()
}

export async function listRuns(){
  const r=await fetch("/runs")
  return r.json()
}

export async function getRunDetail(runId){
  const r=await fetch(`/runs/${runId}`)
  if(!r.ok) throw new Error("run not found")
  return r.json()
}

export async function getRunSummary(runId){
  const r=await fetch(`/runs/${runId}/summary`)
  return r.json()
}

export async function createRun({assignment,submissions,names,emails,rubricFile,maxTotal,thresholds,autoApprove}){
  const fd=new FormData()
  fd.append("assignment",assignment)
  for(const f of submissions) fd.append("submissions",f)
  fd.append("student_names",names.join(","))
  fd.append("student_emails",emails.join(","))
  if(rubricFile) fd.append("rubric_json",rubricFile)
  if(maxTotal!=null) fd.append("max_total",String(maxTotal))
  if(thresholds){
    if(thresholds.cosine!=null) fd.append("cosine_threshold",String(thresholds.cosine))
    if(thresholds.jaccard!=null) fd.append("jaccard_threshold",String(thresholds.jaccard))
    if(thresholds.minConf!=null) fd.append("min_plagiarism_confidence",String(thresholds.minConf))
  }
  if(autoApprove) fd.append("auto_approve","true")
  const r=await fetch("/runs",{method:"POST",body:fd})
  if(!r.ok){
    let msg="failed to create run"
    try{const j=await r.json(); if(j?.detail) msg=j.detail}catch{}
    throw new Error(msg)
  }
  return r.json()
}

export async function startRun(runId){
  const r=await fetch(`/runs/${runId}/start`,{method:"POST"})
  return r.json()
}

export async function patchResult(runId,submissionId,patch){
  const r=await fetch(`/runs/${runId}/results/${submissionId}`,{
    method:"PATCH",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(patch),
  })
  if(!r.ok){
    let msg="failed to edit result"
    try{const j=await r.json(); if(j?.detail) msg=j.detail}catch{}
    throw new Error(msg)
  }
  return r.json()
}

export async function approveRun(runId){
  const r=await fetch(`/runs/${runId}/approve`,{method:"POST"})
  if(!r.ok) throw new Error("failed to approve run")
  return r.json()
}

export function openRunSocket(runId,onMessage){
  const proto=location.protocol==="https:"?"wss:":"ws:"
  const ws=new WebSocket(`${proto}//${location.host}/ws/runs/${runId}`)
  ws.onmessage=(ev)=>{
    try{
      const data=JSON.parse(ev.data)
      onMessage(data)
    }catch{}
  }
  return ws
}


// helper notes:
// getHealth()        -> GET /health, used to show "backend up" + gemini key status.
// listRuns()         -> GET /runs, list of past runs for the sidebar.
// getRunDetail()     -> GET /runs/:id, run + submissions + per-student results.
// getRunSummary()    -> GET /runs/:id/summary, the final summary.json (null until run ends).
// createRun()        -> POST /runs (multipart) - uploads the assignment and submissions
//                       plus parallel arrays of names + emails.
// startRun()         -> POST /runs/:id/start, kicks the GRADING phase (stops at
//                       awaiting_approval).
// patchResult()      -> PATCH a result row to override score/feedback (teacher edit).
// approveRun()       -> POST /runs/:id/approve, kicks the REPORT phase (sends emails).
// openRunSocket()    -> opens the live event websocket. Vite dev server proxies /ws/* to
//                       the FastAPI backend so this works during dev without CORS issues.
