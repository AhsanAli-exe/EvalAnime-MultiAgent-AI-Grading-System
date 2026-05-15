from .storage import append_event

POLICY={
    "min_plagiarism_confidence":0.75,
    "min_rubric_criteria":1,
    "min_grading_text_chars":40,
    "max_zero_score_questions":2,
    "plagiarism_confirmed":{
        "cosine_min":0.5,
        "jaccard_min":0.15,
        "verdicts":["plagiarized","paraphrased"],
    },
}

ETHICS_PRINCIPLES=[
    "Transparency: every prompt, tool call, retry, and token count is written to events.jsonl + sqlite.",
    "Human oversight: any item below confidence thresholds is routed to a human-review queue (this module).",
    "Two-layer plagiarism: a deterministic similarity score is required AS EVIDENCE; an LLM verdict alone never accuses a student.",
    "Determinism where it matters: format compliance is computed by code, never by the LLM.",
    "Honesty constraint: every grader/judge prompt instructs the model 'never invent text the submission does not have'.",
    "Cost responsibility: thinking budgets capped, output tokens capped, image DPI lowered before vision calls.",
    "Contestability: full audit log is exportable, so a contested grade can be reviewed event by event.",
    "Privacy: student data stays on the local machine + SQLite; only the parsed text of an individual submission is sent to Gemini.",
]

def review_items(run_id,summary,policy=None):
    pol=policy or POLICY
    items=[]

    rubric=summary.get("rubric",{}) or {}
    crit=rubric.get("criteria",[]) or []
    if len(crit)<pol["min_rubric_criteria"]:
        items.append({"kind":"thin_rubric","severity":"high","reason":f"rubric only has {len(crit)} criteria"})

    for r in summary.get("grader_results",[]) or []:
        student=r.get("student","?")
        text=r.get("parsed_text","") or ""
        if len(text)<pol["min_grading_text_chars"]:
            items.append({"kind":"low_text_extraction","student":student,"severity":"high","reason":f"only {len(text)} chars of text could be extracted"})
        zero_qs=[c for c in (r.get("criteria_scores",[]) or []) if int(c.get("score",0) or 0)==0]
        if len(zero_qs)>pol["max_zero_score_questions"]:
            items.append({"kind":"many_zero_questions","student":student,"severity":"medium","reason":f"{len(zero_qs)} questions scored 0"})
        if not r.get("criteria_scores"):
            items.append({"kind":"unscorable","student":student,"severity":"high","reason":"grader produced no per-question scores"})

    plag=summary.get("plagiarism",{}) or {}
    for j in plag.get("judgments",[]) or []:
        verdict=j.get("verdict","")
        conf=float(j.get("confidence",0) or 0)
        cos=float(j.get("cosine",0) or 0)
        jac=float(j.get("jaccard",0) or 0)
        rules=pol["plagiarism_confirmed"]
        if verdict in rules["verdicts"]:
            if conf<pol["min_plagiarism_confidence"]:
                items.append({"kind":"plagiarism_low_confidence","pair":[j.get("a"),j.get("b")],"severity":"medium","reason":f"verdict={verdict} but confidence={conf:.2f} < {pol['min_plagiarism_confidence']}"})
            if cos<rules["cosine_min"] or jac<rules["jaccard_min"]:
                items.append({"kind":"plagiarism_weak_evidence","pair":[j.get("a"),j.get("b")],"severity":"high","reason":f"verdict={verdict} but cosine={cos} jaccard={jac} below evidence floor"})

    append_event(run_id,"governance_review",{"policy":pol,"num_items":len(items),"items":items})
    return items


# helper notes:
# POLICY              -> the rule book. Tweak these numbers in ONE place and every
#                        downstream decision changes. Examples:
#                        * min_plagiarism_confidence : below this the verdict is
#                          downgraded to "needs review" instead of an accusation.
#                        * plagiarism_confirmed      : the floor evidence required
#                          before an LLM verdict can be treated as a real finding.
# ETHICS_PRINCIPLES   -> the human-readable governance statement we display in the
#                        UI / docs. Tied 1-to-1 with code behavior so we cannot drift
#                        from the principles silently.
# review_items()      -> the one function the orchestrator calls at the end of a run.
#                        It scans the summary for: thin rubric, low-text extraction,
#                        many zero-score questions, unscorable submissions, and
#                        plagiarism findings that don't meet the evidence floor. The
#                        return value is a list of items each with kind / severity /
#                        reason; these are also logged as one governance_review event
#                        so the auditor can reproduce the call later.
