import json
from ..config import GEMINI_MODEL_FAST
from ..storage import append_event
from ..tools.similarity import compute_similarity
from .base import simple_call

SYSTEM=(
    "You judge plagiarism between two student answers using both numeric signals "
    "and the actual text. Return ONLY JSON: "
    "{\"verdict\":\"plagiarized|paraphrased|coincidental|unclear\","
    "\"confidence\":0.0,\"reason\":\"<=30 words\"}. "
    "High cosine + high jaccard usually means copied. "
    "High cosine + low jaccard often means paraphrased. "
    "Common academic phrasing alone is coincidental, not plagiarism."
)

def investigate(run_id,grader_results,cosine_threshold=0.7,jaccard_threshold=0.2):
    append_event(run_id,"phase_step",{"agent":"plagiarism_investigator","action":"start","num_students":len(grader_results),"cosine_threshold":cosine_threshold,"jaccard_threshold":jaccard_threshold})
    docs=[{"id":r["student"],"text":r.get("parsed_text","")} for r in grader_results]
    sim=compute_similarity(run_id,docs,cosine_threshold=cosine_threshold,jaccard_threshold=jaccard_threshold)

    judgments=[]
    text_by_id={d["id"]:d["text"] for d in docs}
    for flag in sim["flags"]:
        a=flag["a"]
        b=flag["b"]
        user=(
            f"Pair: {a} vs {b}\n"
            f"cosine={flag['cosine']} jaccard={flag['jaccard']}\n\n"
            f"--- {a} text (truncated) ---\n{text_by_id.get(a,'')[:1200]}\n\n"
            f"--- {b} text (truncated) ---\n{text_by_id.get(b,'')[:1200]}\n\n"
            "Return the JSON verdict now."
        )
        data=simple_call(
            run_id,
            agent="plagiarism_investigator",
            system=SYSTEM,
            user=user,
            model=GEMINI_MODEL_FAST,
            max_output=180,
            want_json=True,
        )
        if not isinstance(data,dict):
            data={"verdict":"unclear","confidence":0.0,"reason":"parser_failure"}
        judgments.append({**flag,**data})

    result={"matrix_ids":sim["ids"],"cosine":sim["cosine"],"jaccard":sim["jaccard"],"flags":sim["flags"],"judgments":judgments}
    append_event(run_id,"phase_step",{"agent":"plagiarism_investigator","action":"end","num_flags":len(sim["flags"]),"num_judgments":len(judgments)})
    return result


# helper notes:
# SYSTEM           -> the LLM's job is to look at the numbers AND the texts and pick
#                     one of 4 verdicts. We forbid long replies (<=30 words) to keep
#                     output tokens tiny - one verdict per flagged pair, no waffle.
# investigate()    -> first runs the deterministic compute_similarity over every
#                     student's parsed text. Only flagged pairs (above thresholds)
#                     trigger an LLM call. Pairs that didn't even cross the threshold
#                     never spend an LLM token. The proposal stresses "similarity is
#                     EVIDENCE, never the sole basis"; that is exactly this two-step
#                     design: deterministic flags first, LLM final judgment.
