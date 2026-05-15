import sys
import uuid
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

from backend.db import init_db,insert_run,insert_submission,get_run,list_results
from backend.storage import save_assignment_file,save_submission_file,append_event,write_config
from backend.agents.team import run_team_grading,_read_assignment_text
from backend.tools.format_check import check_format

ASSIGNMENT="data/assignments/2da47f92f490/Assignmnet spring'24.docx"
SUBMISSION="data/demo/22K-4036,Ahsan Ali, BAI-4A, Psych A1.docx"

def section(t):
    print("\n=====",t,"=====")

def main():
    init_db()
    run_id="real_"+uuid.uuid4().hex[:8]
    print("run_id:",run_id)

    section("0) ASSIGNMENT text read")
    a_path=save_assignment_file(run_id,"Assignmnet spring'24.docx",Path(ASSIGNMENT).read_bytes())
    insert_run(run_id,"Assignmnet spring'24.docx",a_path)
    text=_read_assignment_text(run_id,a_path)
    print(f"chars extracted from assignment .docx: {len(text)}")
    print("first 200 chars:",repr(text[:200]))
    assert len(text)>500,"assignment text should now be readable, was getting binary garbage before"

    section("1) FORMAT CHECK scaling (max=8, .docx submission)")
    fmt=check_format(run_id,SUBMISSION,Path(SUBMISSION).read_bytes()[:0].decode("utf-8","ignore"),page_count=0,max_total=8,filename_hint="22K-4036,Ahsan Ali, BAI-4A, Psych A1.docx")
    print(" deductions for .docx submission with max=8:",fmt["deductions"])
    print(" total deduction:",fmt["total_deduction"])
    assert fmt["total_deduction"]<=int(0.40*8),"format deduction must respect 40% cap"
    assert all("wrong file type" not in d["reason"] for d in fmt["deductions"]),".docx must be accepted by default"

    section("2) FORMAT CHECK scaling (max=30, same submission)")
    fmt30=check_format(run_id,SUBMISSION,"",page_count=0,max_total=30,filename_hint="22K-4036,Ahsan Ali")
    print(" deductions:",fmt30["deductions"]," total:",fmt30["total_deduction"])

    section("3) FULL GRADING with max=8, .docx assignment + .docx submission")
    write_config(run_id,{"max_total":8,"auto_approve":False})
    sub_id=uuid.uuid4().hex[:10]
    sub_path=save_submission_file(run_id,sub_id,Path(SUBMISSION).name,Path(SUBMISSION).read_bytes())
    insert_submission(sub_id,run_id,"Ahsan Ali","ahsan@example.com",Path(SUBMISSION).name,sub_path)
    append_event(run_id,"submission_added",{"sub_id":sub_id,"student":"Ahsan Ali"})

    summary=run_team_grading(run_id)
    print(" status:",get_run(run_id)["status"])
    print(" rubric max_total:",summary["rubric"]["max_total"]," criteria:",len(summary["rubric"]["criteria"]))
    results=list_results(run_id)
    r=results[0]
    print(f" score: {r['score']}/{r['max_score']}")
    print(f" feedback: {(r['feedback'] or '')[:300]}")
    print(f" deductions: {r['breakdown']['deductions']}")

    assert r["score"]>0,"score must NOT be 0/8 anymore - student wrote real content"
    print("\nALL REGRESSION CHECKS OK")

if __name__=="__main__":
    main()
