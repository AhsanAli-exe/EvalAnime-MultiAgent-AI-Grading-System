import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ..config import SMTP_HOST,SMTP_PORT,SMTP_USER,SMTP_APP_PASSWORD,EMAIL_DRY_RUN,has_smtp
from ..storage import append_event,save_email

def send_email(run_id,sub_id,to_addr,subject,body):
    append_event(run_id,"tool_call_start",{"tool":"send_email","to":to_addr,"subject":subject})
    saved_path=save_email(run_id,sub_id,subject,body,to_addr)

    if EMAIL_DRY_RUN or not has_smtp() or not to_addr:
        result={"ok":True,"mode":"dry_run","saved_to":saved_path}
        append_event(run_id,"tool_call_end",{"tool":"send_email","mode":"dry_run","saved_to":saved_path})
        return result

    try:
        msg=MIMEMultipart()
        msg["From"]=SMTP_USER
        msg["To"]=to_addr
        msg["Subject"]=subject
        msg.attach(MIMEText(body,"plain"))
        with smtplib.SMTP(SMTP_HOST,SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER,SMTP_APP_PASSWORD)
            s.sendmail(SMTP_USER,[to_addr],msg.as_string())
        result={"ok":True,"mode":"sent","saved_to":saved_path}
    except Exception as e:
        result={"ok":False,"mode":"failed","error":str(e),"saved_to":saved_path}

    append_event(run_id,"tool_call_end",{"tool":"send_email","mode":result["mode"],"ok":result["ok"]})
    return result


# helper notes:
# send_email()  -> the reporter agent calls this for each student.
#                  Step 1: always save the email to data/runs/<id>/emails/<sub_id>.json
#                          so we have a paper trail (and so the UI can show it).
#                  Step 2: if EMAIL_DRY_RUN=1 (default) OR smtp creds are missing OR
#                          the student has no email -> stop here, return "dry_run".
#                  Step 3: otherwise actually send via Gmail SMTP using TLS + app
#                          password. Login failure / network error returns ok=False
#                          but the saved file is still kept.
#                  Every call logs tool_call_start / tool_call_end events for audit.
