import sys
import uuid
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

from backend.db import init_db
from backend.config import SMTP_USER,SMTP_APP_PASSWORD,SMTP_HOST,SMTP_PORT,EMAIL_DRY_RUN,has_smtp
from backend.tools.email_tool import send_email

RECIPIENTS=["ahsanal2072@gmail.com","k224036@nu.edu.pk"]

def main():
    init_db()
    print(f"SMTP_HOST={SMTP_HOST}  SMTP_PORT={SMTP_PORT}")
    print(f"SMTP_USER={SMTP_USER}")
    print(f"SMTP_APP_PASSWORD set: {bool(SMTP_APP_PASSWORD)}  (len={len(SMTP_APP_PASSWORD)})")
    print(f"EMAIL_DRY_RUN={EMAIL_DRY_RUN}  has_smtp()={has_smtp()}")
    if EMAIL_DRY_RUN:
        print("NOTE: EMAIL_DRY_RUN is True, so send_email will only save a file, not send.")
        print("Set EMAIL_DRY_RUN=0 in .env to actually send.")
        return

    run_id="email_smoke_"+uuid.uuid4().hex[:6]
    for to in RECIPIENTS:
        sub_id=uuid.uuid4().hex[:8]
        subject="Evalanime SMTP test"
        body=(
            "Hi,\n\n"
            "This is a test email from Evalanime confirming the Gmail SMTP setup is working.\n"
            f"Sender: {SMTP_USER}\n"
            f"Recipient: {to}\n"
            f"Run ID: {run_id}\n\n"
            "If you got this, real email dispatch is live and the reporter agent will use it.\n\n"
            "Regards,\n"
            "Evalanime"
        )
        print(f"\nsending to {to} ...")
        result=send_email(run_id,sub_id,to,subject,body)
        print("  result:",result)

if __name__=="__main__":
    main()
