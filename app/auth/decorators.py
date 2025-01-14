from flask_login import current_user
from functools import wraps
from flask import render_template, url_for, flash, current_app
from flask_babel import gettext

from . import VIEW_FUNCTIONS_PERMISSIONS


def get_func_identifier(func):
    return func.__module__ + "." + func.__name__


def check_permissions(login=False, confirmed=False, admin=False):
    def decorator(func):    
        @wraps(func)
        def decorated_function(*args, **kwargs):

            new_func = func

            if admin:
                # maximum security level: checks if we're logged in AND have admin rights
                # (confirmation isn't checked since having been made admin implies having been granted permission)
                new_func = check_is_admin(func)

            elif confirmed:
                # medium security level: checks if we're logged in AND confirmed
                new_func = check_is_confirmed(func)

            elif login:
                # minimum security: only check if user is logged in: 
                new_func = check_is_logged_in(func)

            # otherwise: no login required, keep the function as is
            return new_func(*args, **kwargs)


        VIEW_FUNCTIONS_PERMISSIONS[get_func_identifier(func)] = {
            "login": login,
            "confirmed": confirmed,
            "admin": admin
        }

        return decorated_function

    return decorator

# replaces the flask built-in login_required decorator
def check_is_logged_in(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_function

def check_is_confirmed(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()        
        if current_user.is_confirmed is False:
            flash(gettext("Please confirm your account!"), "warning")
            return render_template("auth/inactive.html"), 403
        return func(*args, **kwargs)
    return decorated_function

def check_is_admin(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if current_user.is_admin is False:
            return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)

    return decorated_function
