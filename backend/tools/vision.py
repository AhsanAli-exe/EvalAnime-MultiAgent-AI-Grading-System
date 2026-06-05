import io
import base64
from pathlib import Path
from PIL import Image
from anthropic import Anthropic
from ..config import ANTHROPIC_API_KEY,CLAUDE_MODEL_FAST,CLAUDE_MODEL_PRO
from ..storage import append_event

_client=None

def _get_client():
    global _client
    if _client is None:
        _client=Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client

def _images_from_path(file_path,max_pages=2):
    ext=Path(file_path).suffix.lower().lstrip(".")
    if ext=="pdf":
        import fitz
        doc=fitz.open(file_path)
        imgs=[]
        for i,page in enumerate(doc):
            if i>=max_pages:
                break
            pix=page.get_pixmap(dpi=140)
            imgs.append(Image.frombytes("RGB",(pix.width,pix.height),pix.samples))
        doc.close()
        return imgs
    if ext in ("png","jpg","jpeg","webp","bmp"):
        return [Image.open(file_path).convert("RGB")]
    return []

def _img_to_block(img):
    buf=io.BytesIO()
    img.save(buf,format="JPEG",quality=70)
    return {
        "type":"image",
        "source":{
            "type":"base64",
            "media_type":"image/jpeg",
            "data":base64.b64encode(buf.getvalue()).decode("ascii"),
        },
    }

def analyze_visual(run_id,file_path,question,max_pages=2,max_output_tokens=200,use_pro=False):
    append_event(run_id,"tool_call_start",{"tool":"analyze_visual","file":file_path,"question":question[:80]})
    if not ANTHROPIC_API_KEY:
        result={"ok":False,"error":"ANTHROPIC_API_KEY not set","answer":""}
        append_event(run_id,"tool_call_end",{"tool":"analyze_visual","ok":False})
        return result
    imgs=_images_from_path(file_path,max_pages=max_pages)
    if not imgs:
        result={"ok":False,"error":"no images to analyze","answer":""}
        append_event(run_id,"tool_call_end",{"tool":"analyze_visual","ok":False})
        return result
    blocks=[_img_to_block(i) for i in imgs]
    prompt=f"You are grading. {question}\nReply in <=80 words. Start with YES or NO."
    blocks.append({"type":"text","text":prompt})
    model_name=CLAUDE_MODEL_PRO if use_pro else CLAUDE_MODEL_FAST
    try:
        resp=_get_client().messages.create(
            model=model_name,
            max_tokens=max_output_tokens,
            temperature=0.0,
            messages=[{"role":"user","content":blocks}],
        )
        answer="".join(b.text for b in resp.content if getattr(b,"type",None)=="text").strip()
        in_tok=resp.usage.input_tokens
        out_tok=resp.usage.output_tokens
        result={"ok":True,"answer":answer,"input_tokens":in_tok,"output_tokens":out_tok}
    except Exception as e:
        result={"ok":False,"error":str(e),"answer":""}
    append_event(run_id,"tool_call_end",{"tool":"analyze_visual","ok":result["ok"],"input_tokens":result.get("input_tokens",0),"output_tokens":result.get("output_tokens",0)})
    return result


# helper notes:
# _get_client()         -> creates the Anthropic client once and reuses it.
# _images_from_path()   -> turns a pdf (rendered at low 140 DPI to save tokens) or
#                           a single image file into PIL images. We cap at max_pages=2
#                           on purpose - vision tokens are the expensive part.
# _img_to_block()       -> compresses each image as JPEG quality 70 then encodes as
#                           base64 in Anthropic's image-block format. JPEG compression
#                           keeps input-token cost low vs raw PNG.
# analyze_visual()      -> the one function the agent calls when it needs to "look" at
#                           a submission. By default we use Claude HAIKU 4.5 (cheap)
#                           with temperature=0 so the YES/NO answer is consistent.
#                           Pass use_pro=True to escalate to Sonnet 4.6 for harder
#                           visual questions. We cap max_tokens=200 so it can't ramble.
#                           Usage tokens are logged for spend tracking.
