from flask_login import current_user
from functools import wraps

def check_is_confirmed(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.is_confirmed is False:
            flash(gettext("Please confirm your account!"), "warning")
            return redirect(url_for("accounts.inactive"))
        return func(*args, **kwargs)

    return decorated_function
