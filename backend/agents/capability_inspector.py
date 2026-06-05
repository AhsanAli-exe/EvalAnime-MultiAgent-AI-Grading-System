from ..config import CLAUDE_MODEL_PRO,CLAUDE_MODEL_FAST
from ..storage import append_event
from .base import simple_call

SYSTEM=(
    "You inspect an assignment and classify each question. "
    "Return ONLY JSON of shape: "
    "{\"questions\":[{\"q_id\":\"Q1\",\"text\":\"...\",\"type\":\"text|visual\",\"risks\":[\"...\"]}],"
    "\"format_rules\":[\"...\"],"
    "\"stated_max_marks\":<integer or null>}. "
    "A question is 'visual' if it asks the student to draw/label a diagram. "
    "Risks include things like 'requires OCR if scanned', 'easy to plagiarize', etc. "
    "For 'stated_max_marks': if the assignment text mentions a total mark out of which "
    "this assignment is graded (look for phrases like 'Total: 10 marks', 'Marks: 8', "
    "'out of 20', or sum of per-question marks shown beside each question), return that "
    "integer. If the assignment does not state a total at all, return null."
)

def inspect_assignment(run_id,assignment_text):
    append_event(run_id,"phase_step",{"agent":"capability_inspector","action":"start"})
    user=f"Assignment text:\n---\n{assignment_text[:4000]}\n---\nReturn the JSON now."
    data=simple_call(
        run_id,
        agent="capability_inspector",
        system=SYSTEM,
        user=user,
        model=CLAUDE_MODEL_PRO,
        max_output=2500,
        want_json=True,
        thinking=True,
    )
    if not isinstance(data,dict) or not data:
        append_event(run_id,"inspector_empty_response",{"falling_back_to":"flash"})
        data=simple_call(
            run_id,
            agent="capability_inspector_fallback",
            system=SYSTEM,
            user=user,
            model=CLAUDE_MODEL_FAST,
            max_output=1200,
            want_json=True,
            thinking=False,
        )
    if not isinstance(data,dict):
        data={"questions":[],"format_rules":[],"stated_max_marks":None}
    data.setdefault("questions",[])
    data.setdefault("format_rules",[])
    raw=data.get("stated_max_marks",None)
    try:
        data["stated_max_marks"]=int(raw) if raw not in (None,"") else None
    except (TypeError,ValueError):
        data["stated_max_marks"]=None
    append_event(run_id,"phase_step",{"agent":"capability_inspector","action":"end","num_questions":len(data["questions"]),"stated_max_marks":data["stated_max_marks"]})
    return data


# helper notes:
# SYSTEM            -> the role prompt. We pin the model to a strict JSON shape so the
#                      output is parseable and short. "visual" vs "text" classification
#                      is what later tells the grader whether to call the vision tool.
# inspect_assignment()-> reads the assignment (truncated to 4000 chars to keep tokens
#                      sane) and returns a dict with `questions[]` and `format_rules[]`.
#                      Uses Gemini 2.5 PRO with thinking ON because the classification
#                      is the kind of task where a little reasoning helps. Falls back
#                      to an empty structure if the model misbehaves so the pipeline
#                      never crashes.
