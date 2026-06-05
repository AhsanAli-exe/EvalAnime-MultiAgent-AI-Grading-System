import json
from pypdf import PdfReader
from ..config import CLAUDE_MODEL_FAST
from ..storage import append_event
from ..tools.parsers import parse_any
from ..tools.ocr import ocr_pdf_images
from ..tools.format_check import check_format
from ..tools.vision import analyze_visual
from .base import tool_loop,_extract_json
from ..validation import clamp_criterion_score,clamp

SYSTEM=(
    "You are a strict but fair grader. You will be given an assignment, a rubric, "
    "and the path to one student submission. Format-compliance deductions are ALREADY "
    "computed for you - do NOT add any format-related deductions yourself.\n\n"
    "Required workflow:\n"
    "1. Call read_submission to get the student's text.\n"
    "2. For any question the inspector marked 'visual', call analyze_diagram once.\n"
    "3. Call submit_final_grade with the structured grade. This is REQUIRED to finish.\n\n"
    "Rules:\n"
    "- Use the EXACT q_id values from the rubric.\n"
    "- score must be an integer between 0 and that criterion's max.\n"
    "- level must be one of: excellent, good, weak, poor.\n"
    "- Never invent text the submission does not have.\n"
    "- raw_total must equal the sum of criteria_scores[].score values."
)

TOOL_DECLS=[
    {
        "name":"read_submission",
        "description":"Read the student's submission file. Auto-picks pdf/docx/zip parser. If the PDF text is sparse, auto-falls back to OCR. Returns the extracted text and basic metadata.",
        "parameters":{"type":"object","properties":{},"required":[]},
    },
    {
        "name":"analyze_diagram",
        "description":"Ask the multimodal model whether the submission visually contains the answer to a diagram question. Use ONLY for 'visual' type questions identified by the inspector.",
        "parameters":{
            "type":"object",
            "properties":{
                "question":{"type":"string","description":"Short yes/no question, e.g. 'Does this submission contain a labelled perception-action loop diagram?'"}
            },
            "required":["question"],
        },
    },
    {
        "name":"submit_final_grade",
        "description":"REQUIRED final step. Call this exactly once after you have read the submission (and analyzed any diagrams). Submits the structured grade. The loop ends after this is called.",
        "parameters":{
            "type":"object",
            "properties":{
                "criteria_scores":{
                    "type":"array",
                    "description":"One entry per rubric criterion. Each is an object with q_id, score, max, level, reason.",
                    "items":{
                        "type":"object",
                        "properties":{
                            "q_id":{"type":"string"},
                            "score":{"type":"number","description":"awarded marks, 0..max"},
                            "max":{"type":"number","description":"criterion max from rubric"},
                            "level":{"type":"string","description":"one of excellent, good, weak, poor"},
                            "reason":{"type":"string","description":"under 20 words"},
                        },
                        "required":["q_id","score","max","level","reason"],
                    },
                },
                "raw_total":{"type":"number","description":"sum of criteria_scores.score values"},
                "comments":{"type":"string","description":"short feedback paragraph for the student, under 80 words"},
            },
            "required":["criteria_scores","raw_total","comments"],
        },
    },
]

def _count_pages(file_path):
    try:
        if file_path.lower().endswith(".pdf"):
            return len(PdfReader(file_path).pages)
    except Exception:
        return 0
    return 0

def _make_handlers(run_id,file_path,state):
    def read_submission():
        out=parse_any(run_id,file_path)
        text=out["result"].get("text","")
        sparse=out["result"].get("sparse",False) if out["kind"] in ("pdf","zip+pdf") else False
        actual_path=out.get("inner",file_path)
        if sparse:
            ocr=ocr_pdf_images(run_id,actual_path)
            if ocr["ok"] and len(ocr["text"])>len(text):
                text=ocr["text"]
        state["text"]=text
        state["actual_path"]=actual_path
        state["pages"]=_count_pages(actual_path)
        return {"text":text[:5000],"chars":len(text),"pages":state["pages"],"parser":out["kind"]}
    def analyze_diagram(question):
        path=state.get("actual_path",file_path)
        r=analyze_visual(run_id,path,question,max_pages=1,max_output_tokens=120)
        return {"ok":r["ok"],"answer":r.get("answer","")[:300]}
    def submit_final_grade(criteria_scores,raw_total,comments):
        state["final_grade"]={"criteria_scores":criteria_scores,"raw_total":raw_total,"comments":comments}
        return {"ok":True,"saved":True}
    return {
        "read_submission":read_submission,
        "analyze_diagram":analyze_diagram,
        "submit_final_grade":submit_final_grade,
    }

def _deterministic_format(run_id,file_path,max_total,filename_hint=""):
    pages=_count_pages(file_path)
    text=""
    try:
        out=parse_any(run_id,file_path)
        text=out["result"].get("text","") or ""
        if out["kind"] in ("pdf","zip+pdf") and out["result"].get("sparse"):
            actual=out.get("inner",file_path)
            ocr=ocr_pdf_images(run_id,actual)
            if ocr["ok"] and len(ocr["text"])>len(text):
                text=ocr["text"]
    except Exception:
        pass
    return check_format(run_id,file_path,text,pages,max_total=max_total,filename_hint=filename_hint)

def grade_submission(run_id,submission,assignment_text,rubric,inspection):
    file_path=submission["file_path"]
    student=submission["student_name"]
    file_name=submission.get("file_name","")
    append_event(run_id,"phase_step",{"agent":"submission_grader","action":"start","student":student,"file":file_name})

    max_total=int(rubric.get("max_total") or 30)
    fmt=_deterministic_format(run_id,file_path,max_total,filename_hint=file_name)
    format_deductions=fmt.get("deductions",[])
    format_total=fmt.get("total_deduction",0)

    state={}
    handlers=_make_handlers(run_id,file_path,state)

    user=(
        f"Assignment summary:\n{assignment_text[:1200]}\n\n"
        f"Rubric (JSON):\n{json.dumps(rubric)[:1500]}\n\n"
        f"Inspector findings (JSON):\n{json.dumps(inspection)[:1000]}\n\n"
        f"Student: {student}\n"
        f"Submission file: {submission['file_name']}\n\n"
        f"Pre-computed format deductions (already applied, do NOT repeat): {json.dumps(format_deductions)}\n\n"
        "Use the tools, then return the final grade JSON (criteria_scores + raw_total + comments)."
    )
    text=tool_loop(
        run_id,
        agent=f"submission_grader[{student}]",
        system=SYSTEM,
        user=user,
        tool_decls=TOOL_DECLS,
        tool_handlers=handlers,
        model=CLAUDE_MODEL_FAST,
        max_iters=6,
        max_output=1500,
        thinking_budget=0,
        temperature=0.0,
    )
    data=state.get("final_grade") or _extract_json(text) or {}
    raw_crit=data.get("criteria_scores",[]) or []
    rubric_max_by_qid={c.get("q_id"):int(c.get("max",0) or 0) for c in rubric.get("criteria",[])}
    crit=[]
    for c in raw_crit:
        if not isinstance(c,dict):
            continue
        qid=c.get("q_id")
        cap=rubric_max_by_qid.get(qid)
        if cap is None:
            cap=int(c.get("max",0) or 0)
        clean={
            "q_id":qid or f"Q{len(crit)+1}",
            "score":int(round(clamp_criterion_score(c.get("score",0),cap))),
            "max":cap,
            "level":str(c.get("level","") or "")[:20],
            "reason":str(c.get("reason","") or "")[:200],
        }
        crit.append(clean)

    raw_total=int(clamp(sum(c["score"] for c in crit),0,max_total))
    final_total=int(clamp(raw_total-format_total,0,max_total))

    result={
        "student":student,
        "file":submission["file_name"],
        "criteria_scores":crit,
        "raw_total":raw_total,
        "max_score":max_total,
        "deductions":format_deductions,
        "final_total":final_total,
        "comments":data.get("comments","") if isinstance(data.get("comments"),str) else "",
        "parsed_text":state.get("text",""),
    }
    if not crit:
        result["comments"]=result["comments"] or "Grader could not produce structured per-question scores. Please review manually."
    append_event(run_id,"phase_step",{"agent":"submission_grader","action":"end","student":student,"final_total":final_total,"raw":raw_total,"format_ded":format_total})
    return result


# helper notes:
# SYSTEM            -> tells the LLM it must NOT add format deductions (those are
#                      already done deterministically by us). It only scores the
#                      content per the rubric. Output is strict JSON.
# TOOL_DECLS        -> the two "tools" the model can call: read_submission (auto
#                      pdf/docx/zip parse + OCR fallback) and analyze_diagram (vision).
#                      The model decides if/when to call each one.
# _count_pages()    -> tiny helper, uses pypdf to count pages.
# _make_handlers()  -> binds tools to run_id + file_path so the model never has to
#                      pass paths around (less tokens, fewer mistakes).
# _deterministic_format()-> runs parse_any (with OCR fallback if sparse) then
#                      check_format on the same text. The deductions this returns are
#                      the ONLY format deductions that get applied - exactly matches
#                      the proposal's "format compliance enforced deterministically".
# grade_submission()-> pre-computes format deductions, then runs the agentic tool
#                      loop for content scoring, then combines: final_total = raw_total
#                      - format_total. Returns a clean result dict ready for the DB.
