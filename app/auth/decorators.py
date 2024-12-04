from flask_login import current_user, login_required
from functools import wraps
from flask import redirect, url_for, flash
from flask_babel import gettext

from . import VIEW_FUNCTIONS_PERMISSIONS


def get_func_identifier(func):
    return func.__module__ + "." + func.__name__


def check_permissions(login=False, confirmed=False, admin=False):
    def decorator(func):    
        @wraps(func)
        def decorated_function(*args, **kwargs):
            new_func = func
            
            # order is important here: if we have admin+confirmed+login, login should be the outermost function, or we'll get an error checking for current_user.{is_confirmed,is.admin} 
            if admin:
                new_func = check_is_admin(new_func)
            if confirmed:
                new_func = check_is_confirmed(new_func)
            if login:
                new_func = login_required(new_func)

            return new_func(*args, **kwargs)

        VIEW_FUNCTIONS_PERMISSIONS[get_func_identifier(func)] = {
            "login": login,
            "confirmed": confirmed,
            "admin": admin
        }

        return decorated_function

    return decorator

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
