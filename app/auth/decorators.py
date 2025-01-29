from flask_login import current_user
from functools import wraps
from flask import render_template, url_for, flash, current_app, request
from flask_babel import gettext

from app.utils_db import create_access_log_entry

def get_func_identifier(func):
    return func.__module__ + "." + func.__name__


def log_auth_failure(error_code, error_msg):
    create_access_log_entry(
        current_user.is_authenticated,
        current_user.id if current_user.is_authenticated else -1,
        current_user.is_confirmed if current_user.is_authenticated else False,
        current_user.is_admin if current_user.is_authenticated else False,
        current_user.email if current_user.is_authenticated else None,
        "auth_failure",
        request.endpoint,
        request.url,
        error_code,
        error_msg
    )


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

        return decorated_function

    return decorator

# replaces the flask built-in login_required decorator
def check_is_logged_in(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            log_auth_failure(
                current_app.login_manager.unauthorized_status_code, 
                "unauthenticated user tried to access login-only endpoint"   
            )
            return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_function

def check_is_confirmed(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            log_auth_failure(
                current_app.login_manager.unauthorized_status_code, 
                "unauthenticated user tried to access confirmed-only endpoint"   
            )
            return current_app.login_manager.unauthorized()        
        if current_user.is_confirmed is False:
            flash(gettext("You are trying to access a page that requires your account to be verified."), "warning")
            log_auth_failure(
                403, 
                "unconfirmed user tried to access confirmed-only endpoint"   
            )
            return render_template("auth/inactive.html"), 403
        return func(*args, **kwargs)
    return decorated_function

def check_is_admin(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            log_auth_failure(
                current_app.login_manager.unauthorized_status_code, 
                "unauthenticated user tried to access admin-only endpoint"   
            )
            return current_app.login_manager.unauthorized()
        if current_user.is_admin is False:
            log_auth_failure(
                current_app.login_manager.unauthorized_status_code, 
                "user without admin rights tried to access admin-only endpoint"   
            )
            return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)

    return decorated_function
