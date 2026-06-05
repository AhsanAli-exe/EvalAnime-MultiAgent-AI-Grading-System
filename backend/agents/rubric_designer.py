import json
from ..config import CLAUDE_MODEL_PRO
from ..storage import append_event
from .base import simple_call

SYSTEM=(
    "You design grading rubrics. "
    "Return ONLY JSON of shape: "
    "{\"max_total\":<int>,"
    "\"criteria\":[{\"q_id\":\"Q1\",\"max\":<int>,\"levels\":["
    "{\"label\":\"excellent\",\"min_pct\":0.9,\"desc\":\"...\"},"
    "{\"label\":\"good\",\"min_pct\":0.7,\"desc\":\"...\"},"
    "{\"label\":\"weak\",\"min_pct\":0.4,\"desc\":\"...\"},"
    "{\"label\":\"poor\",\"min_pct\":0.0,\"desc\":\"...\"}]}]}. "
    "Keep desc fields short (under 20 words each). "
    "The sum of the criteria max values MUST exactly equal the requested max_total."
)

def _default_criterion(target_total):
    return {
        "q_id":"Q1",
        "max":target_total,
        "levels":[
            {"label":"excellent","min_pct":0.9,"desc":"Fully addresses every requirement with depth"},
            {"label":"good","min_pct":0.7,"desc":"Mostly addresses requirements, minor gaps"},
            {"label":"weak","min_pct":0.4,"desc":"Partial answer or weak reasoning"},
            {"label":"poor","min_pct":0.0,"desc":"Off-topic, missing, or incorrect"},
        ],
    }

def _normalize(data,target_total):
    if not isinstance(data,dict):
        data={}
    data.setdefault("criteria",[])
    crit=[c for c in data["criteria"] if isinstance(c,dict)]
    for c in crit:
        try:
            c["max"]=max(0,int(c.get("max",0) or 0))
        except (TypeError,ValueError):
            c["max"]=0
    if not crit:
        crit=[_default_criterion(target_total)]
    s=sum(c["max"] for c in crit)
    if s<=0:
        crit[0]["max"]=target_total
        s=target_total
    if s!=target_total:
        scale=target_total/s
        for c in crit:
            c["max"]=max(0,int(round(c["max"]*scale)))
        diff=target_total-sum(c["max"] for c in crit)
        if diff!=0:
            crit[0]["max"]=max(0,crit[0]["max"]+diff)
    data["criteria"]=crit
    data["max_total"]=target_total
    return data

def design_rubric(run_id,assignment_text,inspection,max_total=30):
    append_event(run_id,"phase_step",{"agent":"rubric_designer","action":"start","max_total":max_total})
    user=(
        "Assignment:\n---\n"+assignment_text[:3000]+
        "\n---\nQuestion analysis (from inspector):\n"+json.dumps(inspection)[:1500]+
        f"\nDesign a rubric. The criteria max values MUST sum to exactly {max_total}. Return JSON now."
    )
    data=simple_call(
        run_id,
        agent="rubric_designer",
        system=SYSTEM,
        user=user,
        model=CLAUDE_MODEL_PRO,
        max_output=3000,
        want_json=True,
        thinking=True,
    )
    data=_normalize(data,max_total)
    append_event(run_id,"phase_step",{"agent":"rubric_designer","action":"end","num_criteria":len(data["criteria"]),"max_total":data["max_total"]})
    return data


# helper notes:
# SYSTEM         -> strict JSON shape; we now templatize max_total instead of
#                   hard-coding 30 so the agent respects the teacher's choice.
# _normalize()   -> defensive cleanup. After the LLM replies we:
#                   (1) drop garbage criteria,
#                   (2) coerce each .max to a non-negative int,
#                   (3) if the sum doesn't equal the requested max_total, rescale
#                       proportionally and absorb any rounding error into the first
#                       criterion. Guarantees the returned rubric is internally
#                       consistent.
# design_rubric()-> accepts the per-run max_total from the orchestrator; defaults
#                   to 30 so older call sites still work.


# helper notes:
# SYSTEM         -> strict JSON shape. Each criterion has q_id, max marks, and 4 level
#                   descriptors (excellent/good/weak/poor) with a min-percentage and
#                   a one-line description. Keeping levels short saves tokens.
# design_rubric()-> feeds the assignment + the inspector's question analysis to
#                   Gemini PRO, with thinking ON because rubric design is the kind of
#                   judgement step where short reasoning pays off. Output is parsed
#                   into a Python dict the grader will reuse.
