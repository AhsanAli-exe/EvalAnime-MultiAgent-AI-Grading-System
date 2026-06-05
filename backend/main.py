import json
import uuid
import asyncio
import queue as queue_mod
from typing import List,Optional
from fastapi import FastAPI,UploadFile,File,Form,HTTPException,BackgroundTasks,WebSocket,WebSocketDisconnect,Body
from fastapi.middleware.cors import CORSMiddleware

from .config import has_anthropic
from .db import init_db,insert_run,insert_submission,get_run,list_runs,list_submissions,list_events,list_results,update_result,delete_run
from .storage import save_assignment_file,save_submission_file,append_event,read_summary,write_config,write_rubric,purge_run_files
from .events_bus import publish
from .agents.team import run_team_grading,run_team_report
from .events_bus import subscribe,unsubscribe
from .validation import (
    ValidationError,validate_max_total,clamp_threshold,
    validate_score,validate_feedback,validate_rubric,validate_email,
)

app=FastAPI(title="Evalanime API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"ok":True,"gemini_key_loaded":has_anthropic()}

@app.post("/runs")
async def create_run(
    assignment:UploadFile=File(...),
    submissions:List[UploadFile]=File(...),
    student_names:str=Form(""),
    student_emails:str=Form(""),
    rubric_json:Optional[UploadFile]=File(None),
    max_total:Optional[str]=Form(None),
    cosine_threshold:Optional[str]=Form(None),
    jaccard_threshold:Optional[str]=Form(None),
    min_plagiarism_confidence:Optional[str]=Form(None),
    auto_approve:Optional[str]=Form(None),
):
    if not submissions:
        raise HTTPException(status_code=400,detail="at least one submission is required")
    try:
        cfg={
            "max_total":validate_max_total(max_total,default=30),
            "cosine_threshold":clamp_threshold(cosine_threshold,"cosine_threshold",default=0.7),
            "jaccard_threshold":clamp_threshold(jaccard_threshold,"jaccard_threshold",default=0.2),
            "min_plagiarism_confidence":clamp_threshold(min_plagiarism_confidence,"min_plagiarism_confidence",default=0.75),
            "auto_approve":str(auto_approve or "").lower() in ("1","true","yes","on"),
        }
    except ValidationError as e:
        raise HTTPException(status_code=400,detail=str(e))

    run_id=uuid.uuid4().hex[:12]
    a_bytes=await assignment.read()
    a_path=save_assignment_file(run_id,assignment.filename,a_bytes)
    insert_run(run_id,assignment.filename,a_path)
    append_event(run_id,"run_created",{"assignment":assignment.filename,"num_submissions":len(submissions)})
    write_config(run_id,cfg)
    append_event(run_id,"run_config",cfg)

    rubric_uploaded=False
    if rubric_json is not None and rubric_json.filename:
        raw=await rubric_json.read()
        try:
            parsed=json.loads(raw.decode("utf-8"))
            parsed=validate_rubric(parsed)
            write_rubric(run_id,parsed)
            cfg["max_total"]=int(parsed["max_total"])
            write_config(run_id,cfg)
            rubric_uploaded=True
            append_event(run_id,"rubric_uploaded",{"criteria":len(parsed["criteria"]),"max_total":parsed["max_total"]})
        except (ValidationError,json.JSONDecodeError,UnicodeDecodeError) as e:
            append_event(run_id,"rubric_upload_error",{"error":str(e)})
            raise HTTPException(status_code=400,detail=f"rubric: {e}")

    names=[n.strip() for n in student_names.split(",")] if student_names else []
    raw_emails=[e.strip() for e in student_emails.split(",")] if student_emails else []

    clean_emails=[]
    for i,raw in enumerate(raw_emails):
        try:
            clean_emails.append(validate_email(raw,field=f"email[{i+1}]",allow_empty=True))
        except ValidationError as e:
            raise HTTPException(status_code=400,detail=str(e))

    sub_ids=[]
    sent_count=0
    for i,sub in enumerate(submissions):
        sub_id=uuid.uuid4().hex[:10]
        data=await sub.read()
        if not data:
            append_event(run_id,"submission_rejected",{"file":sub.filename,"reason":"empty file"})
            continue
        path=save_submission_file(run_id,sub_id,sub.filename,data)
        name=names[i] if i<len(names) else f"Student {i+1}"
        email=clean_emails[i] if i<len(clean_emails) else ""
        if email:
            sent_count+=1
        insert_submission(sub_id,run_id,name,email,sub.filename,path)
        append_event(run_id,"submission_added",{"sub_id":sub_id,"student":name,"file":sub.filename,"has_email":bool(email)})
        sub_ids.append(sub_id)

    if not sub_ids:
        raise HTTPException(status_code=400,detail="all submission files were empty")

    return {"run_id":run_id,"submission_ids":sub_ids,"config":cfg,"rubric_uploaded":rubric_uploaded,"emails_provided":sent_count}

@app.get("/runs")
def get_runs():
    return list_runs()

@app.get("/runs/{run_id}")
def get_run_detail(run_id:str):
    run=get_run(run_id)
    if not run:
        raise HTTPException(status_code=404,detail="run not found")
    return {
        "run":run,
        "submissions":list_submissions(run_id),
        "results":list_results(run_id),
    }

@app.get("/runs/{run_id}/events")
def get_run_events(run_id:str):
    run=get_run(run_id)
    if not run:
        raise HTTPException(status_code=404,detail="run not found")
    return list_events(run_id)

def _bg_grading(run_id:str):
    try:
        run_team_grading(run_id)
    except Exception as e:
        append_event(run_id,"run_error",{"error":str(e)})

def _bg_report(run_id:str):
    try:
        run_team_report(run_id)
    except Exception as e:
        append_event(run_id,"run_error",{"error":str(e)})

@app.post("/runs/{run_id}/start")
def start_run(run_id:str,background:BackgroundTasks):
    run=get_run(run_id)
    if not run:
        raise HTTPException(status_code=404,detail="run not found")
    if run["status"] in ("running","running_emails"):
        return {"run_id":run_id,"status":"already_running"}
    append_event(run_id,"run_start_requested",{})
    background.add_task(_bg_grading,run_id)
    return {"run_id":run_id,"status":"started"}

@app.patch("/runs/{run_id}/results/{submission_id}")
def patch_result(run_id:str,submission_id:str,patch:dict=Body(...)):
    run=get_run(run_id)
    if not run:
        raise HTTPException(status_code=404,detail="run not found")
    if run["status"] not in ("awaiting_approval",):
        raise HTTPException(status_code=400,detail=f"cannot edit results while status={run['status']}; edits only allowed during awaiting_approval")

    existing=[r for r in list_results(run_id) if r["submission_id"]==submission_id]
    if not existing:
        raise HTTPException(status_code=404,detail="result row not found for this run+submission")
    max_total=int(existing[0].get("max_score") or 30)

    raw_score=patch.get("score",None)
    raw_feedback=patch.get("feedback",None)
    try:
        clean_score=validate_score(raw_score,max_total) if raw_score is not None else None
        clean_feedback=validate_feedback(raw_feedback) if raw_feedback is not None else None
    except ValidationError as e:
        raise HTTPException(status_code=400,detail=str(e))

    if clean_score is None and clean_feedback is None:
        raise HTTPException(status_code=400,detail="provide score and/or feedback to edit")

    changed=update_result(run_id,submission_id,score=clean_score,feedback=clean_feedback)
    append_event(run_id,"result_edited",{
        "submission_id":submission_id,
        "score":clean_score,
        "feedback_len":len(clean_feedback) if isinstance(clean_feedback,str) else None,
        "max_total":max_total,
    })
    return {"ok":True,"changed":changed,"score":clean_score,"max_total":max_total}

@app.delete("/runs/{run_id}")
def remove_run(run_id:str):
    run=get_run(run_id)
    if not run:
        raise HTTPException(status_code=404,detail="run not found")
    if run["status"] in ("running","running_emails"):
        raise HTTPException(status_code=400,detail=f"cannot delete a run while status={run['status']}")
    publish(run_id,{"kind":"run_deleted","payload":{"run_id":run_id}})
    delete_run(run_id)
    purge_run_files(run_id)
    return {"ok":True,"run_id":run_id}

@app.post("/runs/{run_id}/approve")
def approve_run(run_id:str,background:BackgroundTasks):
    run=get_run(run_id)
    if not run:
        raise HTTPException(status_code=404,detail="run not found")
    if run["status"]!="awaiting_approval":
        raise HTTPException(status_code=400,detail=f"cannot approve: status={run['status']}")
    append_event(run_id,"run_approved",{})
    background.add_task(_bg_report,run_id)
    return {"run_id":run_id,"status":"approved"}

@app.get("/runs/{run_id}/summary")
def get_run_summary(run_id:str):
    run=get_run(run_id)
    if not run:
        raise HTTPException(status_code=404,detail="run not found")
    summary=read_summary(run_id)
    return {"run":run,"summary":summary}

@app.websocket("/ws/runs/{run_id}")
async def ws_run(websocket:WebSocket,run_id:str):
    await websocket.accept()
    run=get_run(run_id)
    if not run:
        await websocket.send_json({"kind":"error","payload":{"error":"run not found"}})
        await websocket.close()
        return

    history=list_events(run_id)
    for ev in history:
        await websocket.send_json({"ts":ev.get("ts",""),"kind":ev.get("kind",""),"payload":ev.get("payload",{})})

    q=subscribe(run_id)
    try:
        while True:
            try:
                ev=await asyncio.to_thread(q.get,True,5)
                await websocket.send_json(ev)
            except queue_mod.Empty:
                await websocket.send_json({"kind":"ping","payload":{}})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        unsubscribe(run_id,q)
        try:
            await websocket.close()
        except Exception:
            pass


# end of code:
# comments:
# app                 : the FastAPI application
# CORSMiddleware      : allow frontend (vite dev server on :5173) to call api freely
# on_startup()        : runs init_db so tables exist before first request
# health()            : simple liveness check + confirms gemini key is loaded
# create_run()        : main upload endpoint - takes assignment + N submissions and creates a run
# get_runs()          : list every run (used by frontend dashboard)
# get_run_detail()    : full info for one run (submissions + results)
# get_run_events()    : the audit-log events for a run (later also streamed via websocket)
# start_run()         : kicks GRADING phase in a background task. POST and forget.
#                       It stops at 'awaiting_approval' so the teacher can review/edit
#                       grades before emails go out (unless auto_approve=true was set
#                       in the create_run config).
# patch_result()      : PATCH /runs/{id}/results/{sub_id} - teacher overrides a score
#                       or comment. Only allowed while the run is still pending.
# approve_run()       : POST /runs/{id}/approve - teacher clicks "Approve & send emails".
#                       Kicks the REPORT phase which reads the (possibly edited) results
#                       and composes + sends one email per student.
# _bg_grading() / _bg_report() : background-task wrappers that turn any exception
#                       into a run_error audit event instead of a silent server log.
# get_run_summary()   : returns the final summary.json (or null if the run hasn't finished)
# ws_run()            : websocket /ws/runs/{id} - first replays the full event history,
#                       then live-streams new events from the in-process bus. Sends a
#                       short "ping" every ~5s of silence so the connection stays warm.
# _parse_float()      : tolerant float parser - empty string / missing -> default.
