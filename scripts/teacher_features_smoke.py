import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

from backend.db import init_db,insert_run,insert_submission,list_results,get_run
from backend.storage import save_assignment_file,save_submission_file,append_event,write_config,write_rubric,read_summary
from backend.scripts.gen_demo import build_all
from backend.agents.team import run_team_grading,run_team_report

BASE="http://127.0.0.1:8000"

TEACHER_RUBRIC={
    "max_total":30,
    "criteria":[
        {"q_id":"Q1","max":10,"levels":[
            {"label":"excellent","min_pct":0.9,"desc":"Defines agent + lists all 4 properties clearly"},
            {"label":"good","min_pct":0.7,"desc":"Defines agent + lists most properties"},
            {"label":"weak","min_pct":0.4,"desc":"Partial definition or missing properties"},
            {"label":"poor","min_pct":0.0,"desc":"Incorrect or absent"},
        ]},
        {"q_id":"Q2","max":10,"levels":[
            {"label":"excellent","min_pct":0.9,"desc":"Clear supervised vs unsupervised explanation with examples"},
            {"label":"good","min_pct":0.7,"desc":"Mostly correct distinction"},
            {"label":"weak","min_pct":0.4,"desc":"Vague or partly wrong"},
            {"label":"poor","min_pct":0.0,"desc":"Wrong or missing"},
        ]},
        {"q_id":"Q3","max":10,"levels":[
            {"label":"excellent","min_pct":0.9,"desc":"Clearly labelled perception-action diagram"},
            {"label":"good","min_pct":0.7,"desc":"Diagram with minor labelling gaps"},
            {"label":"weak","min_pct":0.4,"desc":"Text-only description, no diagram"},
            {"label":"poor","min_pct":0.0,"desc":"Missing or wrong"},
        ]},
    ],
}

def section(t):
    print("\n====",t,"====")

def main():
    init_db()
    n=int(sys.argv[1]) if len(sys.argv)>1 else 3
    info=build_all(subset=n)
    run_id="teach_"+uuid.uuid4().hex[:8]
    print(f"run_id: {run_id}  (using {len(info['submissions'])} submissions)")

    a_path=save_assignment_file(run_id,"assignment.pdf",Path(info["assignment"]).read_bytes())
    insert_run(run_id,"assignment.pdf",a_path)
    append_event(run_id,"run_created",{"assignment":"assignment.pdf","num_submissions":6})

    cfg={"cosine_threshold":0.55,"jaccard_threshold":0.15,"min_plagiarism_confidence":0.80,"auto_approve":False}
    write_config(run_id,cfg)
    append_event(run_id,"run_config",cfg)
    print("config written:",cfg)

    write_rubric(run_id,TEACHER_RUBRIC)
    append_event(run_id,"rubric_uploaded",{"criteria":len(TEACHER_RUBRIC["criteria"])})
    print("teacher rubric written (3 criteria, total 30)")

    for s in info["submissions"]:
        sid=uuid.uuid4().hex[:10]
        sp=save_submission_file(run_id,sid,Path(s["file"]).name,Path(s["file"]).read_bytes())
        insert_submission(sid,run_id,s["name"],s["email"],Path(s["file"]).name,sp)
        append_event(run_id,"submission_added",{"sub_id":sid,"student":s["name"]})

    section("1) GRADING (should skip rubric designer)")
    t0=time.time()
    summary=run_team_grading(run_id)
    print(f"grading done in {time.time()-t0:.1f}s; status now: {get_run(run_id)['status']}")
    print("rubric used (max_total):",summary["rubric"]["max_total"],"criteria:",len(summary["rubric"]["criteria"]))
    print("plag flags:",len(summary["plagiarism"]["flags"]))
    print("governance review_items:",len(summary["governance"]["review_items"]))
    used_pol=summary["governance"]["policy"]
    print(f"effective policy: min_conf={used_pol['min_plagiarism_confidence']} cos_min={used_pol['plagiarism_confirmed']['cosine_min']} jac_min={used_pol['plagiarism_confirmed']['jaccard_min']}")

    section("2) ASSERTS")
    assert get_run(run_id)["status"]=="awaiting_approval","status must be awaiting_approval after grading"
    assert summary["rubric"]==TEACHER_RUBRIC,"teacher rubric must be used as-is"
    assert used_pol["min_plagiarism_confidence"]==0.80,"per-run min_confidence must override default"
    print("ok: status=awaiting_approval, rubric=teacher_uploaded, policy overrides applied")

    section("3) TEACHER EDIT one score via DB")
    from backend.db import update_result,list_submissions
    subs=list_submissions(run_id)
    first_sub=subs[0]
    print(f"editing {first_sub['student_name']} score to 25, feedback updated")
    update_result(run_id,first_sub["id"],score=25,feedback="Overridden by teacher: excellent work despite the diagram quibble.")
    append_event(run_id,"result_edited",{"submission_id":first_sub["id"],"score":25})

    section("4) APPROVE -> RUN REPORT")
    t1=time.time()
    summary2=run_team_report(run_id)
    print(f"report done in {time.time()-t1:.1f}s; status now: {get_run(run_id)['status']}")
    assert get_run(run_id)["status"]=="completed","status must be completed after report"

    emails=summary2.get("emails",[])
    print(f"emails generated: {len(emails)}")
    edited=next((e for e in emails if e["student"]==first_sub["student_name"]),None)
    print("edited student email subject:",edited["subject"] if edited else "(missing)")

    section("5) VERIFY EDIT FLOWED INTO REPORTER")
    res=[r for r in list_results(run_id) if r["submission_id"]==first_sub["id"]][0]
    assert int(res["score"])==25,f"expected 25, got {res['score']}"
    assert "Overridden by teacher" in (res["feedback"] or ""),"feedback override should be persisted"
    print(f"ok: db score={res['score']}, feedback persisted, subject contains edited score: {'(25/' in (edited['subject'] if edited else '')}")

    print("\nALL TEACHER-CONTROL FEATURES OK")

if __name__=="__main__":
    main()
