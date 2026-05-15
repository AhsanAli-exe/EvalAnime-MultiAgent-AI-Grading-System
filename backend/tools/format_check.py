import re
from pathlib import Path
from ..storage import append_event

DEFAULT_RULES={
    "allowed_extensions":["pdf","docx"],
    "min_pages":1,
    "max_pages":50,
    "require_name_field":False,
    "require_roll_field":False,
    "pct_wrong_extension":0.15,
    "pct_pages_out_of_range":0.10,
    "pct_missing_name":0.05,
    "pct_missing_roll":0.05,
    "max_total_deduction_pct":0.40,
}

NAME_PATTERNS=[r"\bname\s*[:\-]",r"\bstudent\s*name\b"]
ROLL_PATTERNS=[r"\broll\s*[:\-]",r"\broll\s*no\b",r"\broll\s*number\b",r"\b\d{2}[a-z]\-?\d{4}\b"]

def _has_any(text,patterns):
    t=(text or "").lower()
    return any(re.search(p,t) for p in patterns)

def _round_points(pct,max_total):
    return max(0,int(round(pct*max(0,max_total))))

def check_format(run_id,file_path,parsed_text,page_count,max_total=30,rules=None,filename_hint=""):
    rules=rules or DEFAULT_RULES
    append_event(run_id,"tool_call_start",{"tool":"check_format","file":file_path,"max_total":max_total})
    deductions=[]

    ext=Path(file_path).suffix.lower().lstrip(".")
    if ext not in rules["allowed_extensions"]:
        d=_round_points(rules["pct_wrong_extension"],max_total)
        if d>0:
            deductions.append({"reason":f"wrong file type: .{ext} (allowed: .{', .'.join(rules['allowed_extensions'])})","points":d})

    if page_count and (page_count<rules["min_pages"] or page_count>rules["max_pages"]):
        d=_round_points(rules["pct_pages_out_of_range"],max_total)
        if d>0:
            deductions.append({"reason":f"page count {page_count} out of allowed range {rules['min_pages']}-{rules['max_pages']}","points":d})

    combined=f"{parsed_text or ''}\n{filename_hint or ''}"
    if rules.get("require_name_field") and not _has_any(combined,NAME_PATTERNS):
        d=_round_points(rules["pct_missing_name"],max_total)
        if d>0:
            deductions.append({"reason":"missing 'Name:' field","points":d})
    if rules.get("require_roll_field") and not _has_any(combined,ROLL_PATTERNS):
        d=_round_points(rules["pct_missing_roll"],max_total)
        if d>0:
            deductions.append({"reason":"missing 'Roll:' field","points":d})

    total=sum(d["points"] for d in deductions)
    cap=_round_points(rules.get("max_total_deduction_pct",0.40),max_total)
    if total>cap:
        deductions.append({"reason":f"format deductions capped at {int(rules.get('max_total_deduction_pct',0.40)*100)}% of max_total","points":-(total-cap)})
        total=cap

    result={"ok":True,"deductions":deductions,"total_deduction":total,"compliant":total==0}
    append_event(run_id,"tool_call_end",{"tool":"check_format","deductions":deductions,"total":total,"compliant":result["compliant"]})
    return result


# helper notes:
# DEFAULT_RULES   -> the rule book. Now permissive by default:
#                    * accepts BOTH .pdf and .docx (most class assignments are one of these)
#                    * Name/Roll fields are NO LONGER required by default (they were
#                      causing harsh deductions on submissions that put info in the
#                      filename or header instead of inline). Teachers can re-enable
#                      them per-run later if they want strict format policing.
#                    * deductions are now PERCENTAGES so they scale with max_total
#                      instead of being absolute (which exploded for small assignments
#                      like max=8).
# _round_points() -> percentage of max_total, rounded, clamped to >=0
# check_format()  -> takes the run's max_total (e.g. 8, 30, 50) and converts each
#                    rule's percentage to an absolute deduction. After the per-rule
#                    deductions are tallied, the GRAND TOTAL is capped at
#                    max_total_deduction_pct (default 40%) - so format mistakes can
#                    NEVER eat more than 40% of the marks. A "cap line" is added to
#                    deductions when the cap kicks in so it's visible in the UI.
#                    filename_hint lets us also check the FILE NAME for roll-number
#                    patterns like "22K-4036" - many students put the info there.