import io
from pathlib import Path
from PIL import Image
from google import genai
from google.genai import types as gtypes
from ..config import GEMINI_API_KEY,GEMINI_MODEL_FAST,GEMINI_MODEL_PRO
from ..storage import append_event

_client=None

def _get_client():
    global _client
    if _client is None:
        _client=genai.Client(api_key=GEMINI_API_KEY)
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

def _img_to_part(img):
    buf=io.BytesIO()
    img.save(buf,format="JPEG",quality=70)
    return gtypes.Part.from_bytes(data=buf.getvalue(),mime_type="image/jpeg")

def analyze_visual(run_id,file_path,question,max_pages=2,max_output_tokens=200,use_pro=False):
    append_event(run_id,"tool_call_start",{"tool":"analyze_visual","file":file_path,"question":question[:80]})
    if not GEMINI_API_KEY:
        result={"ok":False,"error":"GEMINI_API_KEY not set","answer":""}
        append_event(run_id,"tool_call_end",{"tool":"analyze_visual","ok":False})
        return result
    imgs=_images_from_path(file_path,max_pages=max_pages)
    if not imgs:
        result={"ok":False,"error":"no images to analyze","answer":""}
        append_event(run_id,"tool_call_end",{"tool":"analyze_visual","ok":False})
        return result
    parts=[_img_to_part(i) for i in imgs]
    prompt=f"You are grading. {question}\nReply in <=80 words. Start with YES or NO."
    model_name=GEMINI_MODEL_PRO if use_pro else GEMINI_MODEL_FAST
    try:
        client=_get_client()
        resp=client.models.generate_content(
            model=model_name,
            contents=[*parts,prompt],
            config=gtypes.GenerateContentConfig(
                max_output_tokens=max_output_tokens,
                temperature=0.1,
                thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
            ),
        )
        answer=(resp.text or "").strip()
        usage=getattr(resp,"usage_metadata",None)
        in_tok=getattr(usage,"prompt_token_count",0) if usage else 0
        out_tok=getattr(usage,"candidates_token_count",0) if usage else 0
        result={"ok":True,"answer":answer,"input_tokens":in_tok,"output_tokens":out_tok}
    except Exception as e:
        result={"ok":False,"error":str(e),"answer":""}
    append_event(run_id,"tool_call_end",{"tool":"analyze_visual","ok":result["ok"],"input_tokens":result.get("input_tokens",0),"output_tokens":result.get("output_tokens",0)})
    return result


# helper notes:
# _get_client()         -> creates the gemini client once and reuses it (saves time)
# _images_from_path()   -> turns a pdf (rendered at low 140 DPI to save tokens) or
#                           a single image file into PIL images. We cap at max_pages=2
#                           on purpose - vision tokens are the expensive part.
# _img_to_part()        -> compresses each image as JPEG quality 70 before sending.
#                           This drastically cuts the input-token cost vs raw PNG.
# analyze_visual()      -> the one function the agent calls when it needs to "look" at
#                           a submission. By default we use 2.5 FLASH (cheap) with the
#                           "thinking" budget set to 0, so the model goes straight to
#                           the answer with no hidden reasoning tokens. Pass use_pro=True
#                           to escalate to 2.5 Pro for hard visual questions. We also
#                           cap max_output_tokens=200 so it can't ramble, and JPEG-
#                           compress the image to keep input tokens low. The
#                           usage_metadata (input_tokens, output_tokens) is logged so
#                           you can see exactly how many tokens were spent.
