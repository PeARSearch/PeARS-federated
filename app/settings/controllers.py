# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


# Import flask dependencies
import logging
from glob import glob
from os import rename, getenv
from os.path import dirname, realpath, join, isdir, exists
from flask import Blueprint, flash, request, render_template, redirect, url_for, session
from flask_login import current_user, logout_user
from flask_babel import gettext
from app import app, db
from app.api.models import Urls, User
from app.forms import EmailChangeForm, UsernameChangeForm
from app.utils_db import delete_url_representations
from app.auth.decorators import check_permissions
from app.auth.token import send_email


# Define the blueprint:
settings = Blueprint('settings', __name__, url_prefix='/settings')

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = getenv("PODS_DIR", join(dir_path,'pods'))


# Abusing this controller to set maintenance mode
@settings.route("/maintenance")
@check_permissions(login=True, confirmed=True, admin=True)
def toggle_maintenance_mode():
    print("Current status of maintenance:", app.config['MAINTENANCE'])
    if not app.config['MAINTENANCE']:
        print("Switching on maintenance")
        app.config['MAINTENANCE'] = True
    else:
        print("Switching off maintenance")
        app.config['MAINTENANCE'] = False
    return redirect(url_for("search.index"))


# Set the route and accepted methods
@settings.route("/")
@check_permissions(login=True)
def index():
    username = current_user.username
    email = current_user.email
    emailform = EmailChangeForm()
    usernameform = UsernameChangeForm()
    contributions = []
    tips = []
    comments = []

    for i in db.session.query(Urls).filter_by(contributor=username).all():
        url = join(request.host_url,'api','get?url='+i.url)
        if i.pod.split('.u.')[0] == 'Tips':
            tips.append([url, i.title])
        else:
            contributions.append([url, i.title])
    contributions = contributions[::-1] #reverse from most recent
    tips = tips[::-1] #reverse from most recent
    num_contributions = len(contributions)+len(tips)
    
    for i in db.session.query(Urls).filter(Urls.notes.isnot(None)).all():
        url = join(request.host_url,'api','get?url='+i.url)
        notes = ['@'+note.replace('<br>','') for note in i.notes.split('@') if note.startswith(username)]
        note = ' | '.join(notes)
        comments.append([url, note])
    return render_template("settings/index.html", username=username, email=email, num_contributions=num_contributions, contributions=contributions, tips=tips, comments=comments, emailform=emailform, usernameform = usernameform)


@settings.route("/toggle-theme")
def toggle_theme():
    current_theme = session.get("theme")
    print(current_theme, request.args.get('current_page'))
    if current_theme == "dark":
        session["theme"] = "light"
    else:
        session["theme"] = "dark"
    return redirect(request.args.get('current_page'))


@settings.route('/delete', methods=['GET'])
@check_permissions(login=True, confirmed=True, admin=True)
def delete_url():
    username = current_user.username
    url = request.args.get('url').split('get?url=')[1]
    pod = db.session.query(Urls).filter_by(url=url).first().pod
    # Double check url belongs to the user
    contributor = pod.split('.u.')[1]
    if contributor != username:
        flash(gettext("URL does not belong to you and cannot be deleted."))
        return redirect(url_for("settings.index"))
    try:
        delete_url_representations(url)
        flash("URL "+url+gettext(" was successfully deleted."))
    except:
        flash(gettext("There was a problem deleting URL ")+url+gettext(" Please contact your administrator."))
    return redirect(url_for("settings.index"))

@settings.route('/delcomment', methods=['GET'])
@check_permissions(login=True, confirmed=True)
def delete_comment():
    username = current_user.username
    u = request.args.get('url').split('get?url=')[1]
    url = db.session.query(Urls).filter_by(url=u).first()
    notes = ['@'+note for note in url.notes.split('@') if not note.startswith(username)]
    notes = [note for note in notes if note !='@']
    if len(notes) > 0:
        url.notes = '<br>'.join(notes)
    else:
        url.notes = None
    db.session.commit()
    flash(gettext("Your comments for ")+u+gettext(" were successfully deleted."))
    return redirect(url_for("settings.index"))


def rename_user_files(username, new_user):
    for url in db.session.query(Urls).filter_by(contributor = username).all():
        url.contributor = new_user
        url.pod = url.pod.replace(username, new_user)
    d = join(pod_dir, username)
    idxf = join(pod_dir, new_user, username+'.idx')
    if isdir(d):
        rename(d, join(pod_dir, new_user))
    if exists(idxf):
        rename(idxf, join(pod_dir, new_user, new_user+'.idx'))
    files = glob(join(pod_dir, new_user, '*', '*'))
    for f in files:
        fpath = '/'.join(f.split('/')[:-1])
        fname = f.split('/')[-1]
        rename(f, join(fpath, fname.replace(username, new_user)))
    db.session.commit()


def rename_notes(username, new_user):
    notes = ""
    for url in db.session.query(Urls).filter(Urls.notes.isnot(None)).all():
        if '@'+username+' >>' in url.notes:
            notes = url.notes.replace(username+' >>', new_user+' >>')
        url.notes = notes
    db.session.commit()


def email_exists(email):
    email = db.session.query(User).filter_by(email=email).first()
    if email is not None:
        return True
    return False


def username_exists(username):
    username = db.session.query(User).filter_by(username=username).first()
    if username is not None:
        return True
    return False


@settings.route('/delete_account', methods=['GET'])
@check_permissions(login=True)
def delete_account():
    username = current_user.username
    users = db.session.query(User).all()
    idx = [0]
    for u in users:
        if u.username.startswith('deleteduser'):
            idx.append(int(u.username.replace('deleteduser','')))
    new_deleted_user = 'deleteduser'+str(max(idx)+1)
    print(">> CREATING DELETED USER", new_deleted_user)
    rename_notes(username, new_deleted_user)
    rename_user_files(username, new_deleted_user)

    print(">> DELETING ACCOUNT",username)
    current_user.remove()
    db.session.commit()
    flash(gettext("Your account has successfully been deleted."), "success")
    return redirect(url_for("search.index"))


@settings.route('/change_email', methods=['POST'])
@check_permissions(login=True)
def change_email():
    form = EmailChangeForm(request.form)
    if form.validate_on_submit():
        new_email = request.form.get('email')
        if email_exists(new_email):
            flash(gettext("This email already exists."))
            return redirect(url_for("settings.index"))
        html = render_template("auth/email_change.html", new_email = new_email)
        send_email(current_user.email, "PeARS Instance - You requested an email change.", html)
        current_user.email = new_email
        db.session.commit()
        flash(gettext("Your email has been successfully modified."))
        return redirect(url_for("settings.index"))
    print(form.errors)
    return redirect(url_for("settings.index"))


@settings.route('/change_username', methods=['POST'])
@check_permissions(login=True)
def change_username():
    username = current_user.username
    form = UsernameChangeForm(request.form)
    if form.validate_on_submit():
        new_username = request.form.get('username')
        if username_exists(new_username):
            flash(gettext("This username already exists."))
            return redirect(url_for("settings.index"))
        html = render_template("auth/username_change.html", new_username = new_username)
        send_email(current_user.email, "PeARS Instance - You requested a username change.", html)
        rename_notes(username, new_username)
        rename_user_files(username, new_username)
        current_user.username = new_username
        db.session.commit()
        flash(gettext("Your username has been successfully modified."))
        return redirect(url_for("settings.index"))
    print(form.errors)
    return redirect(url_for("settings.index"))
