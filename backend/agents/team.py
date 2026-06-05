import copy
from pathlib import Path
from pypdf import PdfReader
from ..db import get_run,list_submissions,update_run_status,insert_result,list_results
from ..storage import append_event,write_summary,read_summary,read_config,read_rubric
from ..tools.parsers import parse_pdf,parse_docx
from .capability_inspector import inspect_assignment
from .rubric_designer import design_rubric
from .submission_grader import grade_submission
from .plagiarism_investigator import investigate
from .reporter import report_all
from ..governance import review_items,POLICY,ETHICS_PRINCIPLES

PHASES=["INSPECT","DESIGN_RUBRIC","GRADE_EACH","DETECT_PLAGIARISM","GOVERNANCE","AWAITING_APPROVAL","REPORT"]

def _read_assignment_text(run_id,assignment_path):
    p=Path(assignment_path)
    ext=p.suffix.lower()
    if ext==".pdf":
        r=parse_pdf(run_id,str(p))
        return r.get("text","")
    if ext==".docx":
        r=parse_docx(run_id,str(p))
        return r.get("text","")
    if ext in (".txt",".md"):
        return p.read_text(encoding="utf-8",errors="ignore")
    return ""

def _effective_policy(run_cfg):
    pol=copy.deepcopy(POLICY)
    if "min_plagiarism_confidence" in run_cfg:
        pol["min_plagiarism_confidence"]=float(run_cfg["min_plagiarism_confidence"])
    if "cosine_min" in run_cfg:
        pol["plagiarism_confirmed"]["cosine_min"]=float(run_cfg["cosine_min"])
    if "jaccard_min" in run_cfg:
        pol["plagiarism_confirmed"]["jaccard_min"]=float(run_cfg["jaccard_min"])
    return pol

def run_team_grading(run_id):
    run=get_run(run_id)
    if not run:
        raise ValueError("run not found")
    cfg=read_config(run_id)
    append_event(run_id,"phase",{"name":"START","run_id":run_id,"config":cfg})
    update_run_status(run_id,"running")

    submissions=list_submissions(run_id)
    assignment_text=_read_assignment_text(run_id,run["assignment_path"])

    append_event(run_id,"phase",{"name":"INSPECT"})
    inspection=inspect_assignment(run_id,assignment_text)

    max_total=int(cfg.get("max_total") or 30)
    stated=inspection.get("stated_max_marks")
    if stated is not None and int(stated)!=max_total:
        append_event(run_id,"max_marks_mismatch",{"teacher_set":max_total,"assignment_states":int(stated),"resolution":"teacher value used"})
    teacher_rubric=read_rubric(run_id)
    if teacher_rubric:
        append_event(run_id,"phase",{"name":"DESIGN_RUBRIC","skipped":True,"reason":"teacher_uploaded"})
        rubric=teacher_rubric
        max_total=int(rubric.get("max_total") or max_total)
    else:
        append_event(run_id,"phase",{"name":"DESIGN_RUBRIC","max_total":max_total})
        rubric=design_rubric(run_id,assignment_text,inspection,max_total=max_total)

    append_event(run_id,"phase",{"name":"GRADE_EACH","count":len(submissions)})
    grader_results=[]
    for sub in submissions:
        r=grade_submission(run_id,sub,assignment_text,rubric,inspection)
        insert_result(
            run_id,
            sub["id"],
            float(r.get("final_total") or 0),
            float(rubric.get("max_total") or 30),
            {"criteria_scores":r.get("criteria_scores",[]),"deductions":r.get("deductions",[])},
            r.get("comments",""),
        )
        grader_results.append(r)

    append_event(run_id,"phase",{"name":"DETECT_PLAGIARISM"})
    cosine_thr=float(cfg.get("cosine_threshold",0.7))
    jaccard_thr=float(cfg.get("jaccard_threshold",0.2))
    plag=investigate(run_id,grader_results,cosine_threshold=cosine_thr,jaccard_threshold=jaccard_thr)

    pre_summary={
        "run_id":run_id,
        "assignment":run["assignment_name"],
        "num_submissions":len(submissions),
        "config":cfg,
        "inspection":inspection,
        "rubric":rubric,
        "grader_results":grader_results,
        "plagiarism":{
            "matrix_ids":plag.get("matrix_ids",[]),
            "cosine":plag.get("cosine",[]),
            "jaccard":plag.get("jaccard",[]),
            "flags":plag.get("flags",[]),
            "judgments":plag.get("judgments",[]),
        },
        "emails":[],
    }

    append_event(run_id,"phase",{"name":"GOVERNANCE"})
    policy=_effective_policy(cfg)
    review=review_items(run_id,pre_summary,policy=policy)

    summary={
        **pre_summary,
        "grader_results":[{k:v for k,v in r.items() if k!="parsed_text"} for r in grader_results],
        "governance":{
            "policy":policy,
            "principles":ETHICS_PRINCIPLES,
            "review_items":review,
        },
    }
    write_summary(run_id,summary)
    update_run_status(run_id,"awaiting_approval",summary=summary)
    append_event(run_id,"phase",{"name":"AWAITING_APPROVAL","review_items":len(review)})
    return summary

def run_team_report(run_id):
    run=get_run(run_id)
    if not run:
        raise ValueError("run not found")
    summary=read_summary(run_id) or {}
    submissions=list_submissions(run_id)
    submissions_by_name={s["student_name"]:s for s in submissions}
    db_results={r["submission_id"]:r for r in list_results(run_id)}

    grader_results=[]
    for r in summary.get("grader_results",[]):
        sub=submissions_by_name.get(r.get("student",""))
        db_r=db_results.get(sub["id"]) if sub else None
        merged=dict(r)
        if db_r:
            merged["final_total"]=int(db_r.get("score") or 0)
            merged["max_score"]=int(db_r.get("max_score") or summary.get("rubric",{}).get("max_total") or 30)
            merged["comments"]=db_r.get("feedback") or merged.get("comments","")
            bd=db_r.get("breakdown") or {}
            if "criteria_scores" in bd: merged["criteria_scores"]=bd["criteria_scores"]
            if "deductions" in bd: merged["deductions"]=bd["deductions"]
        else:
            merged["max_score"]=int(summary.get("rubric",{}).get("max_total") or 30)
        merged["student_email"]=sub.get("student_email","") if sub else ""
        merged["submission_id"]=sub["id"] if sub else ""
        grader_results.append(merged)

    update_run_status(run_id,"running_emails")
    append_event(run_id,"phase",{"name":"REPORT"})
    plag=summary.get("plagiarism",{})
    emails=report_all(run_id,grader_results,submissions_by_name,plag)

    summary["emails"]=[{k:v for k,v in e.items() if k!="body"} for e in emails]
    write_summary(run_id,summary)
    update_run_status(run_id,"completed",summary=summary)
    append_event(run_id,"phase",{"name":"DONE"})
    return summary

def run_team(run_id):
    summary=run_team_grading(run_id)
    if read_config(run_id).get("auto_approve",False):
        summary=run_team_report(run_id)
    return summary


# helper notes:
# PHASES               -> updated to expose the new AWAITING_APPROVAL state between
#                          GOVERNANCE and REPORT. The frontend uses this list for the
#                          phase tracker.
# _read_assignment_text() -> pulls plain text out of the uploaded assignment PDF.
# _effective_policy()  -> copies the global POLICY and overlays any per-run override
#                          (min_plagiarism_confidence, cosine_min, jaccard_min) coming
#                          from data/runs/<id>/config.json. Original POLICY is never
#                          mutated.
# run_team_grading()   -> INSPECT -> DESIGN_RUBRIC (skipped if teacher uploaded one)
#                          -> GRADE_EACH -> DETECT_PLAGIARISM (using per-run thresholds)
#                          -> GOVERNANCE. Stops at 'awaiting_approval'.
#                          Reporting is intentionally split out so the teacher can
#                          review and edit grades before emails go out.
# run_team_report()    -> Reads the (possibly teacher-edited) results from sqlite,
#                          merges them onto the original grader_results from summary.json,
#                          runs the REPORT phase. Status: awaiting_approval ->
#                          running_emails -> completed.
# run_team()           -> back-compat entry point that does grading + (if the run
#                          opted into auto_approve in its config) also runs report.