import json
from ..config import GEMINI_MODEL_FAST
from ..storage import append_event
from ..tools.email_tool import send_email
from .base import simple_call

SYSTEM=(
    "You write short, kind, personalized feedback emails for student grades. "
    "Tone: respectful, constructive, specific. "
    "Output ONLY a single email body (plain text, no markdown). "
    "Maximum 140 words. Mention the score, 1-2 strengths, 1-2 improvement points. "
    "If a plagiarism note is provided, mention it factually without accusing tone."
)

def _plag_note_for(student,plag):
    if not plag:
        return ""
    for j in plag.get("judgments",[]):
        if student in (j.get("a"),j.get("b")) and j.get("verdict") in ("plagiarized","paraphrased"):
            other=j["b"] if j["a"]==student else j["a"]
            return f"Note: your submission shows {j['verdict']} overlap with {other}. Reason: {j.get('reason','')}"
    return ""

def report_all(run_id,grader_results,submissions_by_name,plag_result):
    append_event(run_id,"phase_step",{"agent":"reporter","action":"start","num_students":len(grader_results)})
    emails=[]
    for r in grader_results:
        student=r["student"]
        sub=submissions_by_name.get(student,{})
        to_addr=sub.get("student_email","")
        sub_id=sub.get("id","")
        plag_note=_plag_note_for(student,plag_result)

        score=r.get("final_total","?")
        max_score=int(r.get("max_score") or r.get("max_total") or 30)
        user=(
            f"Student: {student}\n"
            f"Final score: {score}/{max_score}\n"
            f"Per-question scores: {json.dumps(r.get('criteria_scores',[]))[:600]}\n"
            f"Deductions: {json.dumps(r.get('deductions',[]))[:300]}\n"
            f"Grader comments: {r.get('comments','')[:400]}\n"
            f"Plagiarism note (may be empty): {plag_note}\n\n"
            "Write the email body now."
        )
        body=simple_call(
            run_id,
            agent=f"reporter[{student}]",
            system=SYSTEM,
            user=user,
            model=GEMINI_MODEL_FAST,
            max_output=300,
        )
        subject=f"Your grade for the assignment ({score}/{max_score})"
        delivery=send_email(run_id,sub_id or "unknown",to_addr,subject,body)
        emails.append({
            "student":student,
            "to":to_addr,
            "subject":subject,
            "body":body,
            "delivery":delivery,
        })
    append_event(run_id,"phase_step",{"agent":"reporter","action":"end","emails":len(emails)})
    return emails


# helper notes:
# SYSTEM            -> very small system prompt (kindness + constraints). Capped at 140
#                     words so each email costs ~200 output tokens max.
# _plag_note_for()  -> if the plagiarism investigator flagged this student in a pair
#                     with verdict 'plagiarized' or 'paraphrased', we build a short
#                     factual note that gets inserted into the email prompt.
# report_all()      -> one LLM call per student to compose the email body, then the
#                     send_email tool (dry-run by default - writes file - or actually
#                     sends via SMTP if EMAIL_DRY_RUN=0 and creds are set). Every
#                     email is also saved on disk under data/runs/<id>/emails/ so the
#                     UI can display them and the audit trail is complete.
