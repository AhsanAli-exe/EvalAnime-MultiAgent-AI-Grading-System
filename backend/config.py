import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR=Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR/".env")

DATA_DIR=ROOT_DIR/"data"
ASSIGNMENTS_DIR=DATA_DIR/"assignments"
UPLOADS_DIR=DATA_DIR/"uploads"
RUNS_DIR=DATA_DIR/"runs"
DB_PATH=DATA_DIR/"evalanime.db"

for d in (DATA_DIR,ASSIGNMENTS_DIR,UPLOADS_DIR,RUNS_DIR):
    d.mkdir(parents=True,exist_ok=True)

GEMINI_API_KEY=os.environ.get("GEMINI_API_KEY","")
GEMINI_MODEL_FAST=os.environ.get("GEMINI_MODEL_FAST","gemini-2.5-flash")
GEMINI_MODEL_PRO=os.environ.get("GEMINI_MODEL_PRO","gemini-2.5-pro")

SMTP_HOST=os.environ.get("SMTP_HOST","smtp.gmail.com")
SMTP_PORT=int(os.environ.get("SMTP_PORT","587"))
SMTP_USER=os.environ.get("SMTP_USER","")
SMTP_APP_PASSWORD=os.environ.get("SMTP_APP_PASSWORD","")
EMAIL_DRY_RUN=os.environ.get("EMAIL_DRY_RUN","1")=="1"

def has_gemini():
    return bool(GEMINI_API_KEY)

def has_smtp():
    return bool(SMTP_USER) and bool(SMTP_APP_PASSWORD)


# end of code:
# comments:
# ROOT_DIR        : path of the project root folder
# DATA_DIR        : folder where all data lives
# ASSIGNMENTS_DIR : where assignment files (the question paper) are stored
# UPLOADS_DIR     : where student submissions are stored
# RUNS_DIR        : per-run output folder (events.jsonl, summary.json, emails)
# DB_PATH         : sqlite database file path
# GEMINI_API_KEY  : api key for google gemini (loaded from .env)
# SMTP_*          : gmail smtp settings used by reporter agent later
# EMAIL_DRY_RUN   : if "1", emails are written to files instead of sent
# has_gemini()    : returns True if a key is present
# has_smtp()      : returns True if smtp credentials are present
