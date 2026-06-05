import json
import shutil
from pathlib import Path
from .config import RUNS_DIR,UPLOADS_DIR,ASSIGNMENTS_DIR
from .db import insert_event,now_iso
from .events_bus import publish

def run_folder(run_id):
    p=RUNS_DIR/run_id
    p.mkdir(parents=True,exist_ok=True)
    (p/"emails").mkdir(exist_ok=True)
    return p

def events_path(run_id):
    return run_folder(run_id)/"events.jsonl"

def summary_path(run_id):
    return run_folder(run_id)/"summary.json"

def save_assignment_file(run_id,filename,data_bytes):
    p=ASSIGNMENTS_DIR/run_id
    p.mkdir(parents=True,exist_ok=True)
    out=p/filename
    out.write_bytes(data_bytes)
    return str(out)

def save_submission_file(run_id,sub_id,filename,data_bytes):
    p=UPLOADS_DIR/run_id/sub_id
    p.mkdir(parents=True,exist_ok=True)
    out=p/filename
    out.write_bytes(data_bytes)
    return str(out)

def append_event(run_id,kind,payload):
    ts=now_iso()
    record={"ts":ts,"kind":kind,"payload":payload}
    with open(events_path(run_id),"a",encoding="utf-8") as f:
        f.write(json.dumps(record)+"\n")
    insert_event(run_id,kind,payload)
    publish(run_id,record)

def write_summary(run_id,summary):
    summary_path(run_id).write_text(json.dumps(summary,indent=2),encoding="utf-8")

def read_summary(run_id):
    p=summary_path(run_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def save_email(run_id,sub_id,subject,body,to_addr):
    p=run_folder(run_id)/"emails"
    p.mkdir(parents=True,exist_ok=True)
    out=p/f"{sub_id}.json"
    payload={"to":to_addr,"subject":subject,"body":body}
    out.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    return str(out)

def config_path(run_id):
    return run_folder(run_id)/"config.json"

def rubric_path(run_id):
    return run_folder(run_id)/"rubric.json"

def write_config(run_id,config):
    config_path(run_id).write_text(json.dumps(config,indent=2),encoding="utf-8")

def read_config(run_id):
    p=config_path(run_id)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))

def write_rubric(run_id,rubric):
    rubric_path(run_id).write_text(json.dumps(rubric,indent=2),encoding="utf-8")

def read_rubric(run_id):
    p=rubric_path(run_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def clear_run_dir(run_id):
    p=RUNS_DIR/run_id
    if p.exists():
        shutil.rmtree(p)

def purge_run_files(run_id):
    for base in (RUNS_DIR,UPLOADS_DIR,ASSIGNMENTS_DIR):
        p=base/run_id
        if p.exists():
            shutil.rmtree(p,ignore_errors=True)


# end of code:
# comments:
# run_folder()        : returns (and creates) the data/runs/<run_id>/ folder
# events_path()       : path to events.jsonl (the audit log file)
# summary_path()      : path to summary.json (final run summary)
# config_path()       : path to per-run config.json (teacher thresholds)
# rubric_path()       : path to per-run rubric.json (used if teacher uploaded one)
# save_assignment_file(): saves the assignment/question paper for a run, returns path
# save_submission_file(): saves one student submission file, returns path
# append_event()      : append one event to events.jsonl AND insert into sqlite
# write_summary/read_summary : final summary.json reader/writer
# write_config/read_config   : per-run config (cosine/jaccard/min_confidence overrides).
#                              Empty dict if file missing (caller falls back to defaults).
# write_rubric/read_rubric   : pre-uploaded rubric. read_rubric returns None when the
#                              teacher did NOT upload one; team.py then calls the
#                              Rubric Designer agent.
# save_email()        : save the generated email json for one student
# clear_run_dir()     : delete a run folder (used for cleanup in tests)
