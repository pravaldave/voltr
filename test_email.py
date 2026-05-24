import smtplib
from email.mime.text import MIMEText

SENDER   = "noreply.voltr@gmail.com"
PASSWORD = "rdnsikttgcaeqrje"
TO       = "pravaldave@gmail.com"

msg            = MIMEText("Voltr email test — if you see this it works.")
msg["Subject"] = "Voltr test"
msg["From"]    = SENDER
msg["To"]      = TO

try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER, PASSWORD)
        server.sendmail(SENDER, TO, msg.as_string())
    print("SUCCESS — email sent")
except Exception as e:
    print(f"FAILED — {e}")
