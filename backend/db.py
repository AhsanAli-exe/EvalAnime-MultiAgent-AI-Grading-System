import sqlite3
import json
from datetime import datetime
from .config import DB_PATH

def get_conn():
    conn=sqlite3.connect(DB_PATH)
    conn.row_factory=sqlite3.Row
    return conn

def init_db():
    conn=get_conn()
    c=conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS runs(
        id TEXT PRIMARY KEY,
        assignment_name TEXT,
        assignment_path TEXT,
        status TEXT,
        created_at TEXT,
        updated_at TEXT,
        summary_json TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS submissions(
        id TEXT PRIMARY KEY,
        run_id TEXT,
        student_name TEXT,
        student_email TEXT,
        file_name TEXT,
        file_path TEXT,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        ts TEXT,
        kind TEXT,
        payload_json TEXT,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS results(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        submission_id TEXT,
        score REAL,
        max_score REAL,
        breakdown_json TEXT,
        feedback TEXT,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    )
    """)
    conn.commit()
    conn.close()

def now_iso():
    return datetime.utcnow().isoformat()

def insert_run(run_id,assignment_name,assignment_path):
    conn=get_conn()
    c=conn.cursor()
    ts=now_iso()
    c.execute(
        "INSERT INTO runs(id,assignment_name,assignment_path,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        (run_id,assignment_name,assignment_path,"created",ts,ts),
    )
    conn.commit()
    conn.close()

def update_run_status(run_id,status,summary=None):
    conn=get_conn()
    c=conn.cursor()
    ts=now_iso()
    if summary is None:
        c.execute("UPDATE runs SET status=?,updated_at=? WHERE id=?",(status,ts,run_id))
    else:
        c.execute(
            "UPDATE runs SET status=?,updated_at=?,summary_json=? WHERE id=?",
            (status,ts,json.dumps(summary),run_id),
        )
    conn.commit()
    conn.close()

def insert_submission(sub_id,run_id,student_name,student_email,file_name,file_path):
    conn=get_conn()
    c=conn.cursor()
    c.execute(
        "INSERT INTO submissions(id,run_id,student_name,student_email,file_name,file_path) VALUES(?,?,?,?,?,?)",
        (sub_id,run_id,student_name,student_email,file_name,file_path),
    )
    conn.commit()
    conn.close()

def list_submissions(run_id):
    conn=get_conn()
    rows=conn.execute("SELECT * FROM submissions WHERE run_id=?",(run_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_run(run_id):
    conn=get_conn()
    row=conn.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def list_runs():
    conn=get_conn()
    rows=conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def insert_event(run_id,kind,payload):
    conn=get_conn()
    c=conn.cursor()
    c.execute(
        "INSERT INTO events(run_id,ts,kind,payload_json) VALUES(?,?,?,?)",
        (run_id,now_iso(),kind,json.dumps(payload)),
    )
    conn.commit()
    conn.close()

def list_events(run_id):
    conn=get_conn()
    rows=conn.execute("SELECT * FROM events WHERE run_id=? ORDER BY id ASC",(run_id,)).fetchall()
    conn.close()
    out=[]
    for r in rows:
        d=dict(r)
        d["payload"]=json.loads(d.pop("payload_json"))
        out.append(d)
    return out

def insert_result(run_id,submission_id,score,max_score,breakdown,feedback):
    conn=get_conn()
    c=conn.cursor()
    c.execute(
        "INSERT INTO results(run_id,submission_id,score,max_score,breakdown_json,feedback) VALUES(?,?,?,?,?,?)",
        (run_id,submission_id,score,max_score,json.dumps(breakdown),feedback),
    )
    conn.commit()
    conn.close()

def update_result(run_id,submission_id,score=None,feedback=None,breakdown=None):
    conn=get_conn()
    c=conn.cursor()
    sets=[]
    vals=[]
    if score is not None:
        sets.append("score=?")
        vals.append(float(score))
    if feedback is not None:
        sets.append("feedback=?")
        vals.append(feedback)
    if breakdown is not None:
        sets.append("breakdown_json=?")
        vals.append(json.dumps(breakdown))
    if not sets:
        conn.close()
        return False
    vals.extend([run_id,submission_id])
    c.execute(f"UPDATE results SET {','.join(sets)} WHERE run_id=? AND submission_id=?",vals)
    changed=c.rowcount>0
    conn.commit()
    conn.close()
    return changed

def list_results(run_id):
    conn=get_conn()
    rows=conn.execute("SELECT * FROM results WHERE run_id=?",(run_id,)).fetchall()
    conn.close()
    out=[]
    for r in rows:
        d=dict(r)
        d["breakdown"]=json.loads(d.pop("breakdown_json")) if d.get("breakdown_json") else {}
        out.append(d)
    return out


# end of code:
# comments:
# get_conn()           : opens a sqlite connection with row-dict access
# init_db()            : creates the 4 tables if they do not already exist
# now_iso()            : returns current utc time as iso string for timestamps
# insert_run()         : add a new run row (assignment + status=created)
# update_run_status()  : change a run's status and optionally store summary json
# insert_submission()  : add a row for one student submission inside a run
# list_submissions()   : get all submissions for a given run
# get_run()            : fetch a single run by id (or None)
# list_runs()          : list every run, newest first
# insert_event()       : append an audit-log event for a run (used by tools/agents)
# list_events()        : read back all events for a run, oldest first
# insert_result()      : save the per-student grading result
# update_result()      : edit an existing result row (used when teacher overrides
#                        a score / comment via PATCH). Returns True if a row changed.
# list_results()       : read back all grading results for a run
