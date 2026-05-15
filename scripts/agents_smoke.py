import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

from backend.db import init_db,insert_run,insert_submission,list_submissions,get_run
from backend.storage import save_assignment_file,save_submission_file,append_event,read_summary,write_config
from backend.scripts.gen_demo import build_all
from backend.agents.team import run_team

def section(title):
    print("\n========",title,"========")

def main():
    init_db()
    n=int(sys.argv[1]) if len(sys.argv)>1 else 3
    info=build_all(subset=n)
    run_id="agent_"+uuid.uuid4().hex[:8]
    print(f"agent smoke run_id: {run_id}  (using {len(info['submissions'])} submissions)")

    a_path=save_assignment_file(run_id,"assignment.pdf",Path(info["assignment"]).read_bytes())
    insert_run(run_id,"assignment.pdf",a_path)
    append_event(run_id,"run_created",{"assignment":"assignment.pdf","num_submissions":len(info["submissions"])})
    write_config(run_id,{"auto_approve":True})

    for s in info["submissions"]:
        sub_id=uuid.uuid4().hex[:10]
        path=save_submission_file(run_id,sub_id,Path(s["file"]).name,Path(s["file"]).read_bytes())
        insert_submission(sub_id,run_id,s["name"],s["email"],Path(s["file"]).name,path)
        append_event(run_id,"submission_added",{"sub_id":sub_id,"student":s["name"]})

    section("RUNNING TEAM")
    summary=run_team(run_id)

    section("FINAL SUMMARY")
    print("status:",get_run(run_id)["status"])
    print("num_submissions:",summary["num_submissions"])
    print("rubric criteria:",len(summary["rubric"].get("criteria",[])))
    print("plagiarism flags:",summary["plagiarism"]["flags"])
    print("plagiarism judgments:",summary["plagiarism"]["judgments"])
    print()
    print("Per-student results:")
    for r in summary["grader_results"]:
        print(f"  {r['student']:18s} total={r.get('final_total','?')} raw={r.get('raw_total','?')} deductions={r.get('deductions',[])}")
        print(f"    comments: {r.get('comments','')[:120]}")

    print()
    print("Emails:")
    for e in summary["emails"]:
        print(f"  -> {e['student']:18s} mode={e['delivery'].get('mode')} saved={e['delivery'].get('saved_to')}")

if __name__=="__main__":
    main()
