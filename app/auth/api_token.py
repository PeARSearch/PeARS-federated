import itsdangerous
import secrets
import string
from app import app, db
from app.api.models import User

def generate_api_key_salt():
    return "".join([secrets.choice(string.digits + string.ascii_letters) for _ in range(20)])


def generate_api_token(user):
    if user.api_key_salt is None:
        user.api_key_salt = generate_api_key_salt()
        db.session.commit()

    s = itsdangerous.URLSafeTimedSerializer(app.config["SECRET_KEY"], user.api_key_salt)
    return s.dumps({"id": user.id})


def validate_api_token(username, api_token):
    user = db.session.query(User).filter_by(username=username).first()
    if not user:
        return None, "Invalid API key or username"
    
    s = itsdangerous.URLSafeTimedSerializer(app.config["SECRET_KEY"], user.api_key_salt)
    try:
        data = s.loads(api_token, max_age=3600)
    except itsdangerous.SignatureExpired:
        return None, "Expired API key"
    except itsdangerous.BadSignature:
        return None, "Invalid API key or username"
    if user.id != data["id"]:
        return None, "Username and API key do not match"
    return user, "API key is valid and not expired"

