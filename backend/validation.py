import math
import re

MAX_TOTAL_MIN=1
MAX_TOTAL_MAX=200
FEEDBACK_MAX_CHARS=4000

EMAIL_MIN_LEN=5
EMAIL_MAX_LEN=254
EMAIL_RE=re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

class ValidationError(ValueError):
    def __init__(self,field,message):
        super().__init__(f"{field}: {message}")
        self.field=field
        self.message=message

def clamp(v,lo,hi):
    return max(lo,min(hi,v))

def to_float(value,field,default=None):
    if value is None or value=="":
        if default is None:
            raise ValidationError(field,"is required")
        return float(default)
    try:
        f=float(value)
    except (TypeError,ValueError):
        raise ValidationError(field,f"must be a number, got {value!r}")
    if math.isnan(f) or math.isinf(f):
        raise ValidationError(field,f"must be a finite number, got {value!r}")
    return f

def to_int(value,field,default=None):
    f=to_float(value,field,default)
    return int(f)

def validate_max_total(value,default=30):
    f=to_float(value,"max_total",default)
    if f<MAX_TOTAL_MIN or f>MAX_TOTAL_MAX:
        raise ValidationError("max_total",f"must be between {MAX_TOTAL_MIN} and {MAX_TOTAL_MAX}")
    return int(round(f))

def clamp_threshold(value,field,default,lo=0.0,hi=1.0):
    f=to_float(value,field,default)
    return clamp(f,lo,hi)

def validate_score(value,max_total):
    f=to_float(value,"score")
    if f<0:
        raise ValidationError("score","cannot be negative")
    if f>max_total:
        raise ValidationError("score",f"cannot exceed max_total ({max_total})")
    return f

def validate_email(value,field="email",allow_empty=True):
    if value is None or value=="":
        if allow_empty:
            return ""
        raise ValidationError(field,"is required")
    if not isinstance(value,str):
        raise ValidationError(field,"must be a string")
    v=value.strip()
    if not v:
        if allow_empty:
            return ""
        raise ValidationError(field,"is required")
    if len(v)<EMAIL_MIN_LEN or len(v)>EMAIL_MAX_LEN:
        raise ValidationError(field,f"length must be between {EMAIL_MIN_LEN} and {EMAIL_MAX_LEN}")
    if " " in v:
        raise ValidationError(field,"cannot contain spaces")
    if v.count("@")!=1:
        raise ValidationError(field,"must contain exactly one '@'")
    if not EMAIL_RE.match(v):
        raise ValidationError(field,f"'{v}' is not a valid email address")
    return v

def validate_feedback(value):
    if value is None:
        return None
    if not isinstance(value,str):
        raise ValidationError("feedback","must be a string")
    if len(value)>FEEDBACK_MAX_CHARS:
        raise ValidationError("feedback",f"too long ({len(value)} chars, max {FEEDBACK_MAX_CHARS})")
    return value

def validate_rubric(obj):
    if not isinstance(obj,dict):
        raise ValidationError("rubric","must be a JSON object")
    crit=obj.get("criteria")
    if not isinstance(crit,list) or not crit:
        raise ValidationError("rubric","must have a non-empty criteria array")
    mt=obj.get("max_total")
    if mt is None:
        sum_of_max=sum(int(c.get("max",0) or 0) for c in crit)
        mt=sum_of_max if sum_of_max>0 else 30
        obj["max_total"]=mt
    mt=validate_max_total(mt)
    obj["max_total"]=mt
    for i,c in enumerate(crit):
        if not isinstance(c,dict):
            raise ValidationError(f"rubric.criteria[{i}]","must be an object")
        cmax=c.get("max",0) or 0
        try:
            c["max"]=max(0,int(cmax))
        except (TypeError,ValueError):
            raise ValidationError(f"rubric.criteria[{i}].max","must be a number")
    return obj

def clamp_criterion_score(value,criterion_max):
    try:
        f=float(value or 0)
    except (TypeError,ValueError):
        f=0.0
    return clamp(f,0.0,float(max(0,criterion_max or 0)))


# helper notes:
# ValidationError       -> simple exception carrying the field name. The API layer
#                          turns these into HTTP 400 with a clear message.
# clamp(v,lo,hi)        -> the workhorse. Used for thresholds and per-criterion scores.
# to_float / to_int     -> tolerant numeric parsing. Raises ValidationError on bad input.
# validate_max_total()  -> total marks for an assignment must be an int in [1,200].
# clamp_threshold()     -> any threshold (cosine/jaccard/min_confidence) lives in [0,1].
#                          Out-of-range values are silently clamped (UI sliders already
#                          enforce this; the clamp is defence in depth for the API).
# validate_score()      -> the bug-fix the teacher hit. Score must be 0..max_total.
#                          Raises ValidationError otherwise.
# validate_feedback()   -> feedback must be a string under FEEDBACK_MAX_CHARS chars.
# validate_rubric()     -> sanity-check an uploaded rubric JSON. Auto-fills max_total
#                          from criteria sums if missing; rejects empty / malformed
#                          rubrics; coerces each criterion.max to a non-negative int.
# clamp_criterion_score()-> used by submission_grader to clamp the LLM's per-question
#                          scores to that criterion's `max`. Prevents an LLM that says
#                          score=15 when criterion.max=10.
