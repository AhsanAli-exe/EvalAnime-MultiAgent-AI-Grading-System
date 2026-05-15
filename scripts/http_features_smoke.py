import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from backend.scripts.gen_demo import build_all

BASE="http://127.0.0.1:8000"

def post_multipart(url,fields,files):
    boundary="----HTTPSmoke98765"
    body=bytearray()
    for name,value in fields:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode())
        body.extend(b"\r\n")
    for name,filepath,content_type in files:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"; filename="{Path(filepath).name}"\r\n'.encode())
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(Path(filepath).read_bytes())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    req=urllib.request.Request(url,data=bytes(body),
        headers={"Content-Type":f"multipart/form-data; boundary={boundary}"},method="POST")
    return urllib.request.urlopen(req,timeout=60)

def post_json(url,obj=None):
    data=json.dumps(obj or {}).encode()
    req=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"},method="POST")
    return urllib.request.urlopen(req,timeout=30)

def patch_json(url,obj):
    data=json.dumps(obj).encode()
    req=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"},method="PATCH")
    return urllib.request.urlopen(req,timeout=30)

def get_json(url):
    return json.loads(urllib.request.urlopen(url,timeout=10).read().decode())

def wait_status(run_id,target,timeout=240):
    t0=time.time()
    while time.time()-t0<timeout:
        d=get_json(f"{BASE}/runs/{run_id}")
        st=d["run"]["status"]
        if st==target: return d
        if st=="completed" and target!="completed": return d
        time.sleep(1)
    raise TimeoutError(f"status never reached {target}")

def expect_http_error(label,fn,code=400):
    try:
        r=fn()
        body=r.read().decode()
        print(f"  FAIL {label}: expected {code}, got {r.status}: {body[:200]}")
        return False
    except urllib.error.HTTPError as e:
        msg=e.read().decode()[:200]
        if e.code==code:
            print(f"  OK   {label}: {e.code} {msg}")
            return True
        print(f"  FAIL {label}: expected {code}, got {e.code}: {msg}")
        return False

def main():
    info=build_all(subset=3)
    subs=info["submissions"]
    print(f"== using {len(subs)} submissions ==")

    print("\n== 1) POST /runs with INVALID max_total -> expect 400 ==")
    expect_http_error("max_total=999",
        lambda:post_multipart(BASE+"/runs",
            [("student_names",",".join(s["name"] for s in subs)),("max_total","999")],
            [("assignment",info["assignment"],"application/pdf")]+
            [("submissions",s["file"],"application/octet-stream") for s in subs]))

    print("\n== 2) POST /runs with custom max_total=50 ==")
    r=post_multipart(BASE+"/runs",
        [("student_names",",".join(s["name"] for s in subs)),
         ("student_emails",",".join(s["email"] for s in subs)),
         ("max_total","50"),
         ("cosine_threshold","2.0"),
         ("jaccard_threshold","-0.1"),
         ("min_plagiarism_confidence","0.8")],
        [("assignment",info["assignment"],"application/pdf")]+
        [("submissions",s["file"],"application/octet-stream") for s in subs])
    out=json.loads(r.read().decode())
    run_id=out["run_id"]
    print(f"  ok run_id={run_id} config={out['config']}")
    assert out["config"]["max_total"]==50,"max_total not stored"
    assert out["config"]["cosine_threshold"]==1.0,"cosine should clamp to 1.0"
    assert out["config"]["jaccard_threshold"]==0.0,"jaccard should clamp to 0.0"

    print("\n== 3) START grading and wait for awaiting_approval ==")
    post_json(f"{BASE}/runs/{run_id}/start")
    d=wait_status(run_id,"awaiting_approval")
    print(f"  status={d['run']['status']}")
    res=d["results"]
    print("  results:",[(r["submission_id"],r["score"],r["max_score"]) for r in res])
    assert all(r["max_score"]==50 for r in res),"every result should use max=50"
    assert all(0<=r["score"]<=50 for r in res),"every score should be inside [0,50]"

    print("\n== 4) PATCH invalid scores (must reject) ==")
    target=res[0]["submission_id"]
    expect_http_error("score=60 (>max 50)",
        lambda:patch_json(f"{BASE}/runs/{run_id}/results/{target}",{"score":60}),code=400)
    expect_http_error("score=-1",
        lambda:patch_json(f"{BASE}/runs/{run_id}/results/{target}",{"score":-1}),code=400)
    expect_http_error("score='A+'",
        lambda:patch_json(f"{BASE}/runs/{run_id}/results/{target}",{"score":"A+"}),code=400)
    expect_http_error("score=NaN-ish (string)",
        lambda:patch_json(f"{BASE}/runs/{run_id}/results/{target}",{"score":"NaN"}),code=400)
    expect_http_error("missing score and feedback",
        lambda:patch_json(f"{BASE}/runs/{run_id}/results/{target}",{}),code=400)
    expect_http_error("feedback too long",
        lambda:patch_json(f"{BASE}/runs/{run_id}/results/{target}",{"feedback":"x"*5000}),code=400)

    print("\n== 5) PATCH valid score (47/50) ==")
    body=patch_json(f"{BASE}/runs/{run_id}/results/{target}",{"score":47,"feedback":"Strong work."}).read().decode()
    print("  ok:",body[:200])

    print("\n== 6) Try to edit after status flips: approve and ensure edit blocked ==")
    post_json(f"{BASE}/runs/{run_id}/approve")
    wait_status(run_id,"completed",timeout=120)
    expect_http_error("edit after completed",
        lambda:patch_json(f"{BASE}/runs/{run_id}/results/{target}",{"score":10}),code=400)

    print("\n== 7) Final summary email subject reflects edited score AND custom max ==")
    s=get_json(f"{BASE}/runs/{run_id}/summary")
    emails=s["summary"]["emails"]
    target_email=next((e for e in emails if "47/50" in e.get("subject","")),None)
    print(f"  emails: {len(emails)}, edited subject: {target_email['subject'] if target_email else '(missing)'}")
    assert target_email,"edited 47/50 must appear in subject"

    print("\nALL HTTP VALIDATION TESTS OK")

if __name__=="__main__":
    main()
