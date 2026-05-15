import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

from backend.db import init_db
from backend.scripts.gen_demo import build_all
from backend.tools.parsers import parse_any
from backend.tools.ocr import ocr_pdf_images,_tesseract_available
from backend.tools.format_check import check_format
from backend.tools.similarity import compute_similarity
from backend.tools.vision import analyze_visual
from backend.tools.email_tool import send_email

def section(title):
    print("\n========",title,"========")

def main():
    init_db()
    run_id="smoke_"+uuid.uuid4().hex[:8]
    print("smoke run_id:",run_id)

    info=build_all()
    subs=info["submissions"]

    section("1) PARSERS")
    parsed_docs=[]
    for s in subs:
        out=parse_any(run_id,s["file"])
        text=out["result"].get("text","")
        sparse=out["result"].get("sparse",False) if out["kind"] in ("pdf","zip+pdf") else False
        print(f" {s['name']:18s} kind={out['kind']:10s} chars={len(text):5d} sparse={sparse}")
        parsed_docs.append({"name":s["name"],"file":s["file"],"text":text,"kind":out["kind"],"sparse":sparse})

    section("2) OCR FALLBACK (only on sparse PDFs)")
    print(" tesseract installed:",_tesseract_available())
    for d in parsed_docs:
        if d["sparse"]:
            r=ocr_pdf_images(run_id,d["file"])
            new_text=r.get("text","") if r["ok"] else ""
            print(f"  OCR {d['name']:18s} ok={r['ok']} chars={len(new_text)}")
            if r["ok"] and len(new_text)>len(d["text"]):
                d["text"]=new_text

    section("3) FORMAT CHECK")
    for d in parsed_docs:
        pages=0
        if d["file"].lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
                pages=len(PdfReader(d["file"]).pages)
            except Exception:
                pages=0
        r=check_format(run_id,d["file"],d["text"],pages)
        d["format_deduction"]=r["total_deduction"]
        print(f" {d['name']:18s} compliant={r['compliant']} deduction={r['total_deduction']} reasons={[x['reason'] for x in r['deductions']]}")

    section("4) SIMILARITY (TF-IDF + 5-gram Jaccard)")
    docs_for_sim=[{"id":d["name"],"text":d["text"]} for d in parsed_docs]
    sim=compute_similarity(run_id,docs_for_sim)
    print(" cosine matrix (rounded):")
    ids=sim["ids"]
    for i,row in enumerate(sim["cosine"]):
        print("  ",ids[i][:14].ljust(14),[round(v,2) for v in row])
    print(" flags:",json.dumps(sim["flags"],indent=2))

    section("5) VISION (one call, low tokens)")
    target=next((d for d in parsed_docs if "Frank" in d["name"]),None)
    if target:
        q="Does this submission contain a labelled diagram showing the perception-action loop (sensors -> agent -> actuators -> environment)?"
        v=analyze_visual(run_id,target["file"],q,max_pages=1,max_output_tokens=120)
        print(f" {target['name']} ok={v['ok']} input_tokens={v.get('input_tokens')} output_tokens={v.get('output_tokens')}")
        print(" answer:",v.get("answer","")[:200])

    section("6) EMAIL (dry-run)")
    e=send_email(run_id,"sub_demo","alice@example.com","Your grade","Hi Alice, your assignment is graded. Score: 27/30.")
    print(" email:",e)

    print("\nALL TOOLS OK. events for this run are stored in data/runs/",run_id)

if __name__=="__main__":
    main()
