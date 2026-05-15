import io
from pathlib import Path
from PIL import Image
from ..storage import append_event

def _tesseract_available():
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False

def _pdf_to_images(file_path):
    import fitz
    images=[]
    doc=fitz.open(file_path)
    for page in doc:
        pix=page.get_pixmap(dpi=200)
        img=Image.frombytes("RGB",(pix.width,pix.height),pix.samples)
        images.append(img)
    doc.close()
    return images

def ocr_pdf_images(run_id,file_path):
    append_event(run_id,"tool_call_start",{"tool":"ocr_pdf_images","file":file_path})
    if not _tesseract_available():
        result={"ok":False,"error":"tesseract binary not installed","text":""}
        append_event(run_id,"tool_call_end",{"tool":"ocr_pdf_images","ok":False,"error":result["error"]})
        return result
    import pytesseract
    try:
        images=_pdf_to_images(file_path)
        parts=[]
        for i,img in enumerate(images):
            t=pytesseract.image_to_string(img)
            parts.append(t)
        text="\n".join(parts).strip()
        result={"ok":True,"text":text,"pages":len(images)}
    except Exception as e:
        result={"ok":False,"error":str(e),"text":""}
    append_event(run_id,"tool_call_end",{"tool":"ocr_pdf_images","ok":result["ok"],"chars":len(result.get("text","")),"pages":result.get("pages",0)})
    return result

def ocr_image(run_id,file_path):
    append_event(run_id,"tool_call_start",{"tool":"ocr_image","file":file_path})
    if not _tesseract_available():
        result={"ok":False,"error":"tesseract binary not installed","text":""}
        append_event(run_id,"tool_call_end",{"tool":"ocr_image","ok":False})
        return result
    import pytesseract
    try:
        img=Image.open(file_path)
        text=pytesseract.image_to_string(img).strip()
        result={"ok":True,"text":text}
    except Exception as e:
        result={"ok":False,"error":str(e),"text":""}
    append_event(run_id,"tool_call_end",{"tool":"ocr_image","ok":result["ok"],"chars":len(result.get("text",""))})
    return result


# helper notes:
# _tesseract_available() -> quick check whether the tesseract.exe binary is installed.
#                           If it is missing the OCR call returns a clean error so the
#                           agent can route to "human review" instead of crashing.
# _pdf_to_images()        -> uses PyMuPDF (fitz) to render every page of a PDF into a
#                           Pillow image at 200 DPI. No poppler / no external binary
#                           needed. This is what makes image-only PDFs readable.
# ocr_pdf_images()        -> the main OCR fallback the agent calls when parse_pdf
#                           returns sparse text. Renders pages then runs tesseract on
#                           each one and joins the result.
# ocr_image()             -> OCR for a single image file (kept simple, not used by demo
#                           but useful later for student #5 if they upload a .png/.jpg).
