# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.api.models import User
from app.forms import RegistrationForm, LoginForm, PasswordForgottenForm, PasswordChangeForm
from app import db, OWN_BRAND

from flask import (Blueprint, flash, request, render_template, Response, redirect, url_for)
from app.auth.token import send_email, send_reset_password_email, generate_token, confirm_token
from datetime import datetime

# Define the blueprint:
auth = Blueprint('auth', __name__, url_prefix='/auth')

''' LOGGING OUT '''

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have successfully logged out.", "success")
    return render_template('search/index.html')

''' LOGGING IN '''

@auth.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm(request.form)
    
    if form.validate_on_submit():
        # login code goes here
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        # check if the user actually exists
        # take the user-supplied password, hash it, and compare it to the hashed password in the database
        if not user or not check_password_hash(user.password, password):
            flash('Please check your login details and try again.')
            return redirect(url_for('auth.login')) # if the user doesn't exist or password is wrong, reload the page

        # if the above check passes, then we know the user has the right credentials
        login_user(user)
        welcome = "<b>Welcome, "+current_user.username+"!</b>"
        return render_template('search/index.html', internal_message=welcome)
    else:
        print(form.errors)
        return render_template('auth/login.html', own_brand = OWN_BRAND, form=form)



''' SIGNING UP '''


@auth.route('/signup', methods=['GET','POST'])
def signup():
    form = RegistrationForm(request.form)
    if form.validate_on_submit():

        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        print(email, username)

        user1 = User.query.filter_by(email=email).first() # if this returns a user, then the email already exists in database
        user2 = User.query.filter_by(username=username).first() # if this returns a user, then the username already exists in database

        if user1 : # if a user is found, we want to redirect back to signup page so user can try again
            flash('Email address already exists.')
            return redirect(url_for('auth.signup'))

        if user2 : # if a user is found, we want to redirect back to signup page so user can try again
            flash('Username already exists.')
            return redirect(url_for('auth.signup'))

        print("Signup form correctly validated.")

        # create a new user with the form data. Hash the password so the plaintext version isn't saved.
        new_user = User(email=email, username=username, password=generate_password_hash(password, method='sha256'))

        # generate confirmation email
        token = generate_token(new_user.email)
        confirm_url = url_for("auth.confirm_email", token=token, _external=True)
        html = render_template("auth/confirm_email.html", confirm_url=confirm_url)
        subject = "Please confirm your email"
        send_email(new_user.email, subject, html)

        # add the new user to the database
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)

        flash("A confirmation has been sent via email.", "success")
        return redirect(url_for("auth.inactive"))
    else:
        print(form.errors)
        return render_template('auth/signup.html', own_brand = OWN_BRAND, form=form)

@auth.route("/registration-confirm/<token>")
@login_required
def confirm_email(token):
    if current_user.is_confirmed:
        flash("Account already confirmed.", "success")
        return redirect(url_for("search.index"))
    email = confirm_token(token)
    user = User.query.filter_by(email=current_user.email).first_or_404()
    if user.email == email:
        user.is_confirmed = True
        user.confirmed_on = datetime.now()
        db.session.add(user)
        db.session.commit()
        flash("You have confirmed your account. Thanks!", "success")
    else:
        flash("The confirmation link is invalid or has expired.", "danger")
    return redirect(url_for("search.index"))

@auth.route("/resend")
@login_required
def resend_confirmation():
    if current_user.is_confirmed:
        flash("Your account has already been confirmed.", "success")
        return redirect(url_for("search.index"))
    token = generate_token(current_user.email)
    confirm_url = url_for("auth.confirm_email", token=token, _external=True)
    html = render_template("auth/confirm_email.html", confirm_url=confirm_url)
    subject = "Please confirm your email"
    send_email(current_user.email, subject, html)
    flash("A new confirmation email has been sent.", "success")
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
        subject = "You have requested a password reset"
        send_reset_password_email(user.email, subject, html)

        flash("A link has been sent via email to reset your password.", "success")
        return redirect(url_for('auth.login'))
    else:
        return render_template('auth/password_forgotten.html', own_brand=OWN_BRAND, form=form)

@auth.route("/password-reset-confirm/<token>")
def password_reset(token):
    if current_user.is_authenticated:
        return redirect(url_for('search.index'))
    form = PasswordChangeForm(request.form)
    email = confirm_token(token)
    user = User.query.filter_by(email=email).first_or_404()
    if user.email == email:
        login_user(user)
        return render_template('auth/password_change.html', username=user.username, own_brand=OWN_BRAND, form=form)
    else:
        flash("The confirmation link is invalid or has expired.", "danger")
        return redirect(url_for("auth.password_forgotten"))

@auth.route("/password-change", methods=['GET', 'POST'])
@login_required
def password_change():
    form = PasswordChangeForm(request.form)
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=current_user.email).first_or_404()
        password = request.form.get('password')
        user.password=generate_password_hash(password, method='sha256')
        db.session.commit()
        flash("Your password has been successfully changed.", "success")
        return redirect(url_for("search.index"))
    else:
        return render_template('auth/password_change.html', own_brand=OWN_BRAND, form=form)



''' INACTIVE '''

@auth.route("/inactive")
@login_required
def inactive():
    if current_user.is_confirmed:
        return redirect(url_for("search.index"))
    return render_template("auth/inactive.html", own_brand=OWN_BRAND)

