import smtplib
from email.mime.text import MIMEText

from app.config import get_settings

settings = get_settings()


def send_email(to_email, subject, body):

    if not settings.smtp_host:
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:

        server.starttls()

        server.login(settings.smtp_user, settings.smtp_password)

        server.sendmail(settings.smtp_from, [to_email], msg.as_string())
