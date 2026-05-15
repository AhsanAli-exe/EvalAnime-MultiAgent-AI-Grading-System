from ..config import GEMINI_MODEL_PRO
from ..storage import append_event
from .base import simple_call

SYSTEM=(
    "You inspect an assignment and classify each question. "
    "Return ONLY JSON of shape: "
    "{\"questions\":[{\"q_id\":\"Q1\",\"text\":\"...\",\"type\":\"text|visual\",\"risks\":[\"...\"]}],"
    "\"format_rules\":[\"...\"]}. "
    "A question is 'visual' if it asks the student to draw/label a diagram. "
    "Risks include things like 'requires OCR if scanned', 'easy to plagiarize', etc."
)

def inspect_assignment(run_id,assignment_text):
    append_event(run_id,"phase_step",{"agent":"capability_inspector","action":"start"})
    user=f"Assignment text:\n---\n{assignment_text[:4000]}\n---\nReturn the JSON now."
    data=simple_call(
        run_id,
        agent="capability_inspector",
        system=SYSTEM,
        user=user,
        model=GEMINI_MODEL_PRO,
        max_output=600,
        want_json=True,
        thinking=True,
    )
    if not isinstance(data,dict):
        data={"questions":[],"format_rules":[]}
    data.setdefault("questions",[])
    data.setdefault("format_rules",[])
    append_event(run_id,"phase_step",{"agent":"capability_inspector","action":"end","num_questions":len(data["questions"])})
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
