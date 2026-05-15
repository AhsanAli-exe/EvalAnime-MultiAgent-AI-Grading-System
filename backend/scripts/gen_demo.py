import io
import zipfile
from pathlib import Path
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from PIL import Image,ImageDraw,ImageFont
from docx import Document

DEMO_DIR=Path(__file__).resolve().parent.parent.parent/"data"/"demo"
DEMO_DIR.mkdir(parents=True,exist_ok=True)

ASSIGNMENT_TEXT=[
    "Assignment 1 - Intro to AI",
    "Course: Agentic AI",
    "Submission rules: PDF only, 1-3 pages, must include name and roll number on first page.",
    "",
    "Q1. Define an intelligent agent and list its 4 main properties. (10 marks)",
    "Q2. Explain the difference between supervised and unsupervised learning. (10 marks)",
    "Q3. Draw and label the perception-action loop of an agent. (10 marks - DIAGRAM REQUIRED)",
]

IDEAL_ANSWERS=[
    "Name: Alice Johnson    Roll: 22K0001",
    "",
    "Q1. An intelligent agent is an entity that perceives its environment through sensors",
    "and acts upon that environment using actuators to achieve goals. The four main",
    "properties are: autonomy, reactivity, pro-activeness, and social ability.",
    "",
    "Q2. Supervised learning uses labeled training data where each input has a known",
    "output, while unsupervised learning works on unlabeled data and tries to find",
    "hidden structure or grouping in it. Examples: classification vs clustering.",
    "",
    "Q3. The perception-action loop: the agent observes the environment via sensors,",
    "updates its internal state, the reasoning module decides on an action, and the",
    "actuators execute that action which changes the environment.",
    "[Diagram included: Environment -> Sensors -> Agent -> Actuators -> Environment]",
]

DOCX_ANSWERS=[
    "Name: Bob Smith    Roll: 22K0002",
    "",
    "Q1. An intelligent agent is a system that perceives its environment using sensors",
    "and then acts upon that environment through actuators in order to achieve goals.",
    "Its four key properties are autonomy, reactivity, pro-activeness, and social ability.",
    "",
    "Q2. Supervised learning relies on labeled training data where each input has a known",
    "target value, while unsupervised learning has no labels and tries to discover hidden",
    "structure or groups within the data. Classification is supervised, clustering is",
    "unsupervised.",
    "",
    "Q3. The perception-action loop works as follows: sensors collect data from the",
    "environment, the agent reasons about the data using its internal state, then",
    "actuators perform actions that change the environment, and the cycle repeats.",
]

PARAPHRASED_OF_BOB=[
    "Name: Charlie Davis    Roll: 22K0003",
    "",
    "Q1. An intelligent agent is a system that perceives its environment using sensors",
    "and then acts upon that environment through actuators in order to achieve goals.",
    "Its four main properties are autonomy, reactivity, pro-activeness, and social ability.",
    "",
    "Q2. Supervised learning relies on labeled training examples where each input has a",
    "known target value, while unsupervised learning has no labels and tries to find",
    "hidden structure or groupings inside the data. Classification is supervised while",
    "clustering is unsupervised.",
    "",
    "Q3. The perception-action loop works like this: sensors collect data from the",
    "environment, the agent reasons about that data using its internal state, then",
    "actuators perform actions that change the environment, and the loop repeats.",
]

NESTED_PDF_ANSWERS=[
    "Name: Diana Patel    Roll: 22K0004",
    "",
    "Q1. An intelligent agent is software that senses and acts. Properties: autonomy,",
    "reactivity, pro-activeness, social ability.",
    "Q2. Supervised: labeled data, predict label. Unsupervised: no labels, discover groups.",
    "Q3. Loop: Environment -> Sensors -> Agent reasoning -> Actuators -> Environment.",
]

PARTIAL_NO_DIAGRAM=[
    "Name: Frank Lee    Roll: 22K0006",
    "",
    "Q1. An intelligent agent perceives and acts in an environment.",
    "Properties: autonomy, reactivity, pro-activeness, social ability.",
    "",
    "Q2. Supervised learning learns from labeled data. Unsupervised learning",
    "finds patterns in unlabeled data.",
    "",
    "Q3. (skipped - no diagram provided)",
]

OCR_TEXT_FOR_IMAGE=[
    "Name: Eve Williams  Roll: 22K0005",
    "Q1. An intelligent agent senses and acts.",
    "Properties: autonomy, reactivity, proactiveness, social ability.",
    "Q2. Supervised uses labels, unsupervised does not.",
    "Q3. Env -> Sensors -> Agent -> Actuators -> Env.",
]

def make_text_pdf(path,lines):
    c=canvas.Canvas(str(path),pagesize=LETTER)
    width,height=LETTER
    y=height-72
    for line in lines:
        c.drawString(72,y,line)
        y-=18
        if y<72:
            c.showPage()
            y=height-72
    c.save()

def make_docx(path,lines):
    doc=Document()
    for line in lines:
        doc.add_paragraph(line)
    doc.save(str(path))

def make_image_pdf(path,lines):
    img=Image.new("RGB",(900,1200),"white")
    draw=ImageDraw.Draw(img)
    try:
        font=ImageFont.truetype("arial.ttf",22)
    except Exception:
        font=ImageFont.load_default()
    y=60
    for line in lines:
        draw.text((60,y),line,fill="black",font=font)
        y+=40
    buf=io.BytesIO()
    img.save(buf,format="PDF")
    Path(path).write_bytes(buf.getvalue())

def make_zip_with_pdf(zip_path,inner_pdf_name,lines):
    tmp_pdf=DEMO_DIR/"_tmp_inner.pdf"
    make_text_pdf(tmp_pdf,lines)
    with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
        z.write(tmp_pdf,arcname=inner_pdf_name)
    tmp_pdf.unlink(missing_ok=True)

def build_all(subset=None):
    assignment_path=DEMO_DIR/"assignment.pdf"
    make_text_pdf(assignment_path,ASSIGNMENT_TEXT)

    s1=DEMO_DIR/"student1_alice.pdf"
    make_text_pdf(s1,IDEAL_ANSWERS)

    s2=DEMO_DIR/"student2_bob.docx"
    make_docx(s2,DOCX_ANSWERS)

    s3=DEMO_DIR/"student3_charlie.pdf"
    make_text_pdf(s3,PARAPHRASED_OF_BOB)

    s4=DEMO_DIR/"student4_diana.zip"
    make_zip_with_pdf(s4,"diana_answers.pdf",NESTED_PDF_ANSWERS)

    s5=DEMO_DIR/"student5_eve_scanned.pdf"
    make_image_pdf(s5,OCR_TEXT_FOR_IMAGE)

    s6=DEMO_DIR/"student6_frank_partial.pdf"
    make_text_pdf(s6,PARTIAL_NO_DIAGRAM)

    all_subs=[
        {"name":"Alice Johnson","email":"alice@example.com","file":str(s1)},
        {"name":"Bob Smith","email":"bob@example.com","file":str(s2)},
        {"name":"Charlie Davis","email":"charlie@example.com","file":str(s3)},
        {"name":"Diana Patel","email":"diana@example.com","file":str(s4)},
        {"name":"Eve Williams","email":"eve@example.com","file":str(s5)},
        {"name":"Frank Lee","email":"frank@example.com","file":str(s6)},
    ]
    if subset:
        all_subs=all_subs[:int(subset)]
    return {"assignment":str(assignment_path),"submissions":all_subs}

if __name__=="__main__":
    info=build_all()
    print("Demo files written to:",DEMO_DIR)
    print("Assignment:",info["assignment"])
    for s in info["submissions"]:
        print(" -",s["name"],"->",s["file"])


# end of code:
# comments:
# DEMO_DIR              : where all generated demo files go (data/demo)
# ASSIGNMENT_TEXT       : the question paper content (shared by every student)
# IDEAL_ANSWERS         : student 1, ideal pdf submission (gold path)
# DOCX_ANSWERS          : student 2, written as .docx -> triggers format deduction
# PARAPHRASED_OF_BOB    : student 3, similar wording to student 2 -> plagiarism flag
# NESTED_PDF_ANSWERS    : student 4, will be zipped with a pdf inside -> unzip path
# PARTIAL_NO_DIAGRAM    : student 6, missing Q3 diagram -> vision/missing-content path
# OCR_TEXT_FOR_IMAGE    : student 5, rendered as an image-pdf (no extractable text) -> OCR path
# make_text_pdf()       : writes a normal text pdf via reportlab
# make_docx()           : writes a .docx via python-docx
# make_image_pdf()      : draws text onto a Pillow image and saves as pdf (no text layer)
# make_zip_with_pdf()   : creates a .zip that contains one inner pdf
# build_all()           : generates everything and returns a manifest dict
