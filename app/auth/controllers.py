# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import os
import io
from markupsafe import Markup
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.api.models import User
from app.forms import RegistrationForm, LoginForm, PasswordForgottenForm, PasswordChangeForm
from app import app, db
from captcha.image import ImageCaptcha
from flask import (Blueprint, flash, request, render_template, Response, redirect, url_for, session, abort)
from flask_babel import gettext
from datetime import datetime
from app.auth.decorators import check_permissions
import random
import string
from app.auth.token import send_email, send_reset_password_email, generate_token, confirm_token
from app.auth.captcha import AudioCaptchaWithOptionalNoise, mk_captcha, check_captcha, refresh_captcha, captcha_dir


# Initialize captcha library
image = ImageCaptcha()
audio = AudioCaptchaWithOptionalNoise()

# Define the blueprint:
auth = Blueprint('auth', __name__, url_prefix='/auth')

''' LOGGING OUT '''

@auth.route('/logout')
@check_permissions(login=True)
def logout():
    logout_user()
    flash(gettext("You have successfully logged out."), "success")
    return redirect(url_for("search.index"))


''' LOGGING IN '''

@auth.route('/login', methods=['GET','POST'])
def login():
    new_users_allowed = app.config['NEW_USERS']
    form = LoginForm(request.form)
    
    if form.validate_on_submit():
        # login code goes here
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        # check if the user actually exists
        # take the user-supplied password, hash it, and compare it to the hashed password in the database
        try:
            if not user or not check_password_hash(user.password, password):
                flash(gettext('Please check your login details and try again.'))
                return redirect(url_for('auth.login')) # if the user doesn't exist or password is wrong, reload the page
        except: #the check_password_hash method has failed
            flash(gettext("We have moved to a more secure authentification method. Please request a password change."))
            return redirect(url_for('auth.password_forgotten'))

        # if the above check passes, then we know the user has the right credentials
        login_user(user)
        if current_user.is_authenticated and not current_user.is_confirmed:
            msg = Markup(gettext("You have not confirmed your account.<br>\
                    Please use the link in the email that was sent to you, \
                    or request a new link by clicking <a href='../auth/resend'>here</a>."))
            flash(msg)
        else:
            welcome = "<b>"+gettext('Welcome')+", "+current_user.username+"!</b>"
        return redirect(url_for("search.index"))
    print(form.errors)
    return render_template('auth/login.html', form=form, new_users_allowed=new_users_allowed)



''' SIGNING UP '''


@auth.route('/signup', methods=['GET','POST'])
def signup():
    new_users_allowed = app.config['NEW_USERS']
    form = RegistrationForm(request.form)
    if form.validate_on_submit():

        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        captcha_id = request.form.get('captcha_id')
        captcha_user_answer = request.form.get('captcha_answer')

        user1 = User.query.filter_by(email=email).first() # if this returns a user, then the email already exists in database
        user2 = User.query.filter_by(username=username).first() # if this returns a user, then the username already exists in database

        if user1 : # if a user is found, we want to redirect back to signup page so user can try again
            flash(gettext('Email address already exists.'))
            return redirect(url_for('auth.signup'))

        if user2 : # if a user is found, we want to redirect back to signup page so user can try again
            flash(gettext('Username already exists.'))
            return redirect(url_for('auth.signup'))

        if not check_captcha(captcha_id, captcha_user_answer):
            flash(gettext('The captcha was incorrectly answered.'))
            return redirect(url_for('auth.signup'))

        # create a new user with the form data. Hash the password so the plaintext version isn't saved.
        new_user = User(email=email, username=username, password=generate_password_hash(password, method='scrypt'))

        # generate confirmation email
        token = generate_token(new_user.email)
        confirm_url = url_for("auth.confirm_email", token=token, _external=True)
        html = render_template("auth/confirm_email.html", confirm_url=confirm_url)
        subject = gettext("Please confirm your email.")
        send_email(new_user.email, subject, html)

        # alert admin (assume for now the admin's address is the default sender)
        admin_mail = app.config["MAIL_DEFAULT_SENDER"]
        sitename = app.config["SITENAME"]
        subject = f"New signup on your PeARS instance: {sitename}"
        html = f"User: {username}, email: {email}"
        send_email(admin_mail, subject, html)

        # add the new user to the database
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)

        flash(gettext("Welcome! Your signup is almost complete; confirm your email address to fully activate your account."), "success")
        return redirect(url_for("auth.inactive"))
    else:
        print("FORM ERRORS:", form.errors)

        # generate captcha (public code/private string pair)
        captcha_id, captcha_correct_answer = mk_captcha()

        form = RegistrationForm(request.form)
        form.captcha_id.data = captcha_id
        return render_template('auth/signup.html', form=form, new_users_allowed=new_users_allowed)

@auth.route("/registration-confirm/<token>")
@check_permissions(login=True)
def confirm_email(token):
    if current_user.is_confirmed:
        flash(gettext("Account already confirmed."), "success")
        return redirect(url_for("search.index"))
    email = confirm_token(token)
    user = User.query.filter_by(email=current_user.email).first_or_404()
    if user.email == email:
        user.is_confirmed = True
        user.confirmed_on = datetime.now()
        db.session.add(user)
        db.session.commit()
        flash(gettext("You have confirmed your account. Thanks!"), "success")
    else:
        flash(gettext("The confirmation link is invalid or has expired."), "danger")
    return redirect(url_for("search.index"))

@auth.route("/resend")
@check_permissions(login=True)
def resend_confirmation():
    if current_user.is_confirmed:
        flash(gettext("Your account has already been confirmed."), "success")
        return redirect(url_for("search.index"))
    token = generate_token(current_user.email)
    confirm_url = url_for("auth.confirm_email", token=token, _external=True)
    html = render_template("auth/confirm_email.html", confirm_url=confirm_url)
    subject = gettext("Please confirm your email.")
    send_email(current_user.email, subject, html)
    flash(gettext("A new confirmation email has been sent."), "success")
    return redirect(url_for("auth.inactive"))



''' PASSWORD FORGOTTEN '''

@auth.route('/password-forgotten', methods=['GET','POST'])
def password_forgotten():
    form = PasswordForgottenForm(request.form)
    
    if form.validate_on_submit():
        # code to validate and add user to database goes here
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first() # if this returns a user, then the email exists in database

        # generate confirmation email
        token = generate_token(user.email)
        confirm_url = url_for("auth.password_reset", token=token, _external=True)
        html = render_template("auth/password_reset_email.html", confirm_url=confirm_url)
        subject = gettext("You have requested a password reset.")
        send_reset_password_email(user.email, subject, html)

        flash(gettext("A link has been sent via email to reset your password."), "success")
        return redirect(url_for('auth.login'))
    else:
        return render_template('auth/password_forgotten.html', form=form)

@auth.route("/password-reset-confirm/<token>")
def password_reset(token):
    if current_user.is_authenticated:
        return redirect(url_for('search.index'))
    form = PasswordChangeForm(request.form)
    email = confirm_token(token)
    if email is not None:
        user = User.query.filter_by(email=email).first()
        if user.email == email:
            login_user(user)
            return render_template('auth/password_change.html', username=user.username, form=form)
        else:
            flash(gettext("The confirmation link is invalid or has expired."), "danger")
            return redirect(url_for("auth.password_forgotten"))
    else:
        flash(gettext("The confirmation link is invalid or has expired."), "danger")
        return redirect(url_for("auth.password_forgotten"))


@auth.route("/password-change", methods=['GET', 'POST'])
@check_permissions(login=True)
def password_change():
    form = PasswordChangeForm(request.form)
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=current_user.email).first_or_404()
        password = request.form.get('password')
        user.password=generate_password_hash(password, method='scrypt')
        db.session.commit()
        flash(gettext("Your password has been successfully changed."), "success")
        return redirect(url_for("search.index"))
    else:
        return render_template('auth/password_change.html', form=form)



''' INACTIVE '''

@auth.route("/inactive")
@check_permissions(login=True)
def inactive():
    if current_user.is_confirmed:
        return redirect(url_for("search.index"))
    return render_template("auth/inactive.html")



''' CAPTCHA '''

@auth.route("/show_captcha/<string:captcha_id>")
def captcha_view(captcha_id):

    # is this a refresh request?
    if request.args.get("refresh", "false") == "true":
        captcha_str = refresh_captcha(captcha_id)

    else:
        captcha_file = os.path.join(captcha_dir, f"{captcha_id}.txt")
        if not os.path.isfile(captcha_file):
            return redirect("/static/captcha-not-found.png")

        with open(captcha_file) as f:
            captcha_str = f.read()

    # captcha is missing (could happen if you try to refresh an expired captcha)
    if captcha_str is None:
        return redirect("/static/captcha-not-found.png")

    if request.args.get("audio", "false") == "true":
        audio_data = io.BytesIO(audio.generate(captcha_str))
        return Response(audio_data, mimetype="audio/wav")

    img_data = image.generate(captcha_str)
    return Response(img_data, mimetype="image/png")
