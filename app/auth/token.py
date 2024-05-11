from itsdangerous import URLSafeTimedSerializer
from flask_mail import Message
from app import app, mail, mail_logger
import os

def generate_token(email):
    serializer = URLSafeTimedSerializer(os.getenv("SECRET_KEY"))
    return serializer.dumps(email, salt=os.getenv("SECURITY_PASSWORD_SALT"))


def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(os.getenv("SECRET_KEY"))
    try:
        email = serializer.loads(
            token, salt=os.getenv("SECURITY_PASSWORD_SALT"), max_age=expiration
        )
        return email
    except Exception:
        return False

def send_email(to, subject, template):
    msg = Message(
        subject,
        recipients=[to],
        html=template,
        sender=app.config["MAIL_DEFAULT_SENDER"],
    )
    mail.send(msg)
    mail_logger.mailing(f"Mailed {to} with subject {subject}")

def send_reset_password_email(to, subject, template):
    msg = Message(
        subject,
        recipients=[to],
        html=template,
        sender=app.config["MAIL_DEFAULT_SENDER"],
    )
    mail.send(msg)
    mail_logger.mailing(f"Mailed {to} with subject {subject}.")

