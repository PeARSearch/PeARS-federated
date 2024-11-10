from flask_login import current_user
from functools import wraps
from flask import redirect, url_for, flash
from flask_babel import gettext

def check_is_confirmed(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.is_confirmed is False:
            flash(gettext("Please confirm your account!"), "warning")
            return redirect(url_for("auth.inactive"))
        return func(*args, **kwargs)

    return decorated_function

def check_is_admin(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.is_admin is False:
            flash(gettext("The page you requested is admin only."), "warning")
            return redirect(url_for("search.index"))
        return func(*args, **kwargs)

    return decorated_function
