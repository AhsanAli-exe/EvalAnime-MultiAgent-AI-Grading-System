import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

from backend.validation import (
    ValidationError,validate_max_total,clamp_threshold,
    validate_score,validate_feedback,validate_rubric,
    clamp_criterion_score,
)
from backend.agents.rubric_designer import _normalize

PASS=0
FAIL=0

def expect_ok(label,fn):
    global PASS,FAIL
    try:
        out=fn()
        print(f"  OK   {label} -> {out!r}")
        PASS+=1
    except Exception as e:
        print(f"  FAIL {label} -> {type(e).__name__}: {e}")
        FAIL+=1

def expect_raises(label,fn,exc=ValidationError):
    global PASS,FAIL
    try:
        out=fn()
        print(f"  FAIL {label} should have raised {exc.__name__}, returned {out!r}")
        FAIL+=1
    except exc as e:
        print(f"  OK   {label} -> raised {type(e).__name__}({e})")
        PASS+=1

def section(t):
    print("\n=====",t,"=====")

def main():
    section("validate_max_total")
    expect_ok("default 30",lambda:validate_max_total(None))
    expect_ok("int 50",lambda:validate_max_total("50"))
    expect_ok("float 99.6 rounds to 100",lambda:validate_max_total("99.6"))
    expect_raises("0 too low",lambda:validate_max_total("0"))
    expect_raises("201 too high",lambda:validate_max_total("201"))
    expect_raises("negative",lambda:validate_max_total("-5"))
    expect_raises("garbage string",lambda:validate_max_total("abc"))

    section("clamp_threshold")
    expect_ok("default 0.7",lambda:clamp_threshold(None,"cosine_threshold",default=0.7))
    expect_ok("0.5 stays",lambda:clamp_threshold("0.5","cosine_threshold",default=0.7))
    expect_ok("2.0 clamps to 1.0",lambda:clamp_threshold("2.0","cosine_threshold",default=0.7))
    expect_ok("-0.3 clamps to 0.0",lambda:clamp_threshold("-0.3","cosine_threshold",default=0.7))
    expect_raises("garbage rejects",lambda:clamp_threshold("xyz","cosine_threshold",default=0.7))

    section("validate_score (the bug fix)")
    expect_ok("15 with max=30",lambda:validate_score(15,30))
    expect_ok("0 with max=30",lambda:validate_score(0,30))
    expect_ok("30 with max=30",lambda:validate_score(30,30))
    expect_raises("35 > 30 should reject",lambda:validate_score(35,30))
    expect_raises("-1 should reject",lambda:validate_score(-1,30))
    expect_raises("string 'A+' should reject",lambda:validate_score("A+",30))
    expect_raises("None should reject",lambda:validate_score(None,30))
    expect_ok("score with max=50 allows 50",lambda:validate_score(50,50))
    expect_raises("score 51 with max=50",lambda:validate_score(51,50))

    section("validate_feedback")
    expect_ok("normal text",lambda:validate_feedback("nice work"))
    expect_ok("None ok",lambda:validate_feedback(None))
    expect_ok("empty string",lambda:validate_feedback(""))
    expect_raises("non-string",lambda:validate_feedback({"a":1}))
    expect_raises("too long",lambda:validate_feedback("x"*5000))

    section("validate_rubric")
    good={"max_total":30,"criteria":[{"q_id":"Q1","max":10},{"q_id":"Q2","max":20}]}
    expect_ok("valid rubric",lambda:validate_rubric(dict(good)))
    expect_raises("empty criteria",lambda:validate_rubric({"max_total":30,"criteria":[]}))
    expect_raises("not a dict",lambda:validate_rubric([]))
    expect_raises("bad criterion",lambda:validate_rubric({"max_total":30,"criteria":["nope"]}))
    expect_ok("missing max_total derives from criteria",lambda:validate_rubric({"criteria":[{"q_id":"Q1","max":5},{"q_id":"Q2","max":7}]}))
    expect_raises("max_total too big",lambda:validate_rubric({"max_total":9999,"criteria":[{"q_id":"Q1","max":10}]}))

    section("clamp_criterion_score (LLM hallucination guard)")
    expect_ok("12 clamped to 10",lambda:clamp_criterion_score(12,10))
    expect_ok("-3 clamped to 0",lambda:clamp_criterion_score(-3,10))
    expect_ok("nan defaults to 0",lambda:clamp_criterion_score(None,10))
    expect_ok("string '8' parses",lambda:clamp_criterion_score("8",10))

    section("rubric_designer._normalize (rescale to target_total)")
    rubric_loose={"criteria":[{"q_id":"Q1","max":5},{"q_id":"Q2","max":5}]}
    n=_normalize(dict(rubric_loose,criteria=[dict(c) for c in rubric_loose["criteria"]]),50)
    expect_ok(f"rescaled to 50 (sum={sum(c['max'] for c in n['criteria'])})",lambda:n["max_total"]==50 and sum(c["max"] for c in n["criteria"])==50)
    n2=_normalize({"criteria":[{"q_id":"Q1","max":3},{"q_id":"Q2","max":3},{"q_id":"Q3","max":4}]},30)
    expect_ok(f"rescaled (10) to 30 with rounding fix",lambda:n2["max_total"]==30 and sum(c["max"] for c in n2["criteria"])==30)

    print(f"\nTOTAL: {PASS} passed, {FAIL} failed")
    sys.exit(0 if FAIL==0 else 1)

if __name__=="__main__":
    main()
