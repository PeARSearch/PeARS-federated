# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


import logging
from glob import glob
from os import rename, getenv
from os.path import dirname, realpath, join, isdir, exists
from markupsafe import Markup
from flask import Blueprint, flash, request, render_template, redirect, url_for, session
from flask_login import current_user, logout_user
from flask_babel import gettext, refresh as babel_refresh
import app as app_module
from app.extensions import db
from app.search.cross_instance_search import filter_instances_by_language
from app.api.models import Urls, Pods, User
from app.forms import EmailChangeForm, UsernameChangeForm, NewContentForm, WebSourceForm
from app.utils_db import delete_url_representations
from app.auth.decorators import check_permissions
from app.auth.token import send_email


# Define the blueprint:
settings = Blueprint('settings', __name__, url_prefix='/settings')

dir_path = dirname(dirname(realpath(__file__)))
app_dir_path = dirname(dir_path)
maintenance_mode_file = getenv("MAINTENANCE_MODE_FILE", join(app_dir_path, '.maintenance_mode'))
pod_dir = getenv("PODS_DIR", join(dir_path,'pods'))
logger = logging.getLogger(__name__)


def get_maintance_mode():
    if not exists(maintenance_mode_file):
        return False
    with open(maintenance_mode_file, 'r', encoding='utf-8') as f:
        maintenance_setting = f.read().strip()
        assert maintenance_setting in ["TRUE", "FALSE"], "Maintenance setting file got corrupted, please change the file content manually back to 'TRUE' or 'FALSE'!"
        return maintenance_setting == "TRUE"


def set_maintenance_mode(mode):
    with open(maintenance_mode_file, 'w', encoding='utf-8') as f:
        if mode:
            f.write("TRUE")
        else:
            f.write("FALSE")


# Abusing this controller to set maintenance mode
@settings.route("/maintenance")
@check_permissions(login=True, confirmed=True, admin=True)
def toggle_maintenance_mode():
    maintenance_mode = get_maintance_mode()
    logger.info("Current status of maintenance: %s", maintenance_mode)
    if not maintenance_mode:
        logger.info("Switching on maintenance")
        set_maintenance_mode(True)
    else:
        logger.info("Switching off maintenance")
        set_maintenance_mode(False)
    return redirect(url_for("search.index"))


@settings.route("refresh_remotes")
@check_permissions(login=True, confirmed=True, admin=True)
def refresh_remote_instances():
    try:
        app_module.instances, app_module.M, skipped_instances = filter_instances_by_language()
        skip_text = '<li style="margin-bottom:0.5em;"><a href="{}">{}</a><br><code style="font-size:0.85em;color:var(--muted-foreground);">{}</code></li>'
        message = gettext("The list of remote instances was successfully refreshed.")
        if skipped_instances:
            message += '<br>' + gettext('Some instances were skipped:') + '<ul style="margin-top:0.5em;padding-left:1.5em;">'
        for skipped in skipped_instances:
            message += skip_text.format(skipped["instance"], skipped["instance"], skipped["reason"])
        if skipped_instances:
            message += "</ul>"
        flash(Markup(message), "success")
    except Exception as e:
        flash(gettext(f"An error occurred while refreshing the list of remote instances: {e}"), "error")
    return redirect(url_for("search.index"))


@settings.route("/")
@check_permissions(login=True)
def index():
    username = current_user.username
    email = current_user.email
    emailform = EmailChangeForm()
    usernameform = UsernameChangeForm()
    contributions = []
    comments = []
    indexed_urls = []
    short_notes = []

    for i in db.session.query(Urls).filter_by(contributor=username).all():
        if i.url.startswith('content'):
            display_url = join(request.host_url,'api','show?url='+i.url)
            contributions.append([display_url, i.title, i.url])
        elif i.url.startswith('comment'):
            display_url = join(request.host_url,'api','show?url='+i.url)
            comments.append([display_url, i.title, i.url])
        else:
            display_url = join(request.host_url,'api','get?url='+i.url)
            indexed_urls.append([display_url, i.title, i.url])
    contributions = contributions[::-1] #reverse from most recent
    comments = comments[::-1]
    indexed_urls = indexed_urls[::-1]
    num_contributions = len(contributions)+len(indexed_urls)+len(comments)
    for i in db.session.query(Urls).filter(Urls.notes.isnot(None)).all():
        display_url = join(request.host_url,'api','get?url='+i.url)
        notes = ['@'+note.replace('<br>','') for note in i.notes.split('@') if note.startswith(username)]
        note = ' | '.join(notes)
        short_notes.append([display_url, note, i.url])
    return render_template("settings/index.html", username=username, email=email, num_contributions=num_contributions, \
            contributions=contributions, urls=indexed_urls, comments=comments, notes=short_notes, emailform=emailform, usernameform=usernameform)


@settings.route("/toggle-theme")
def toggle_theme():
    current_theme = session.get("theme")
    logger.debug("%s %s", current_theme, request.args.get('current_page'))
    if current_theme == "dark":
        session["theme"] = "light"
    else:
        session["theme"] = "dark"
    return redirect(request.args.get('current_page'))


@settings.route("/set-language")
def set_language():
    from app import AVAILABLE_UI_LANGUAGES
    lang = request.args.get('lang')
    if lang and lang in AVAILABLE_UI_LANGUAGES:
        session['locale'] = lang
        babel_refresh()
    return redirect(request.args.get('current_page', url_for('search.index')))


@settings.route('/delete', methods=['GET'])
@check_permissions(login=True, confirmed=True)
def delete_url():
    username = current_user.username
    url = request.args.get('url')
    entry = db.session.query(Urls).filter_by(url=url).first()
    if not url or not entry:
        flash(gettext("Content not found."), "danger")
        return redirect(url_for("settings.index"))
    pod = entry.pod
    # Double check url belongs to the user
    contributor = pod.split('.u.')[1]
    if contributor != username:
        flash(gettext("URL does not belong to you and cannot be deleted."), "danger")
        return redirect(url_for("settings.index"))
    try:
        delete_url_representations(url)
        flash("URL "+url+gettext(" was successfully deleted."), "success")
    except:
        flash(gettext("There was a problem deleting URL ")+url+gettext(" Please contact your administrator."), "danger")
    return redirect(url_for("settings.index"))


@settings.route('/editcontent', methods=['GET'])
@check_permissions(login=True, confirmed=True)
def edit_content():
    '''Open edit page so that user can change their
    content.'''
    num_db_entries = len(Urls.query.all())
    username = current_user.username
    u = request.args.get('url')
    url = db.session.query(Urls).filter_by(url=u).first()
    if not u or not url:
        flash(gettext("Content not found."), "danger")
        return redirect(url_for("settings.index"))
    # Double check url belongs to the user
    if url.contributor != username:
        flash(gettext("URL does not belong to you and cannot be edited."), 'danger')
        return redirect(url_for("settings.index"))
    pods = Pods.query.all()
    themes = list({p.name.split('.u.')[0] for p in pods})
    content = Markup(url.content.replace('<br>', '\n')).unescape() #unescaping should be safe since escaping will happen again on submit
    form = NewContentForm(title=url.title, content=content, theme=url.pod.split('.u.')[0], chosen_license=url.url_license)
    return render_template('indexer/write_and_index.html', num_entries=num_db_entries, form=form, themes=themes)


@settings.route('/editcomment', methods=['GET'])
@check_permissions(login=True, confirmed=True)
def edit_comment():
    '''Open edit page so that user can change their
    comment.'''
    num_db_entries = len(Urls.query.all())
    username = current_user.username
    u = request.args.get('url')
    url = db.session.query(Urls).filter_by(url=u).first()
    if not u or not url:
        flash(gettext("Content not found."), "danger")
        return redirect(url_for("settings.index"))
    # Double check url belongs to the user
    if url.contributor != username:
        flash(gettext("URL does not belong to you and cannot directly be edited. You can however add a note to the existing record."), 'danger')
        return redirect(url.share)
    pods = Pods.query.all()
    themes = list({p.name.split('.u.')[0] for p in pods})
    description = Markup(url.content.replace('<br>', '\n')).unescape() #unescaping should be safe since escaping will happen again on submit
    form = WebSourceForm(title=url.title, description=description, related_url=url.share, theme=url.pod.split('.u.')[0], chosen_license=url.url_license)
    return render_template('indexer/web_commentary.html', num_entries=num_db_entries, form=form, themes=themes)


@settings.route('/deletenotes', methods=['GET'])
@check_permissions(login=True, confirmed=True)
def delete_notes():
    username = current_user.username
    u = request.args.get('url')
    url = db.session.query(Urls).filter_by(url=u).first()
    if not u or not url or not url.notes:
        flash(gettext("Content not found."), "danger")
        return redirect(url_for("settings.index"))
    notes = ['@'+note for note in url.notes.split('@') if not note.startswith(username)]
    notes = [note for note in notes if note !='@']
    if len(notes) > 0:
        url.notes = '<br>'.join(notes)
    else:
        url.notes = None
    db.session.commit()
    flash(gettext("Your notes for ")+u+gettext(" were successfully deleted."), "success")
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
    for url in db.session.query(Urls).filter(Urls.notes.isnot(None)).all():
        if '@'+username+' >>' in url.notes:
            url.notes = url.notes.replace(username+' >>', new_user+' >>')
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
            suffix = u.username.replace('deleteduser', '')
            try:
                idx.append(int(suffix))
            except ValueError:
                continue
    new_deleted_user = 'deleteduser'+str(max(idx)+1)
    logger.info("Creating deleted user %s", new_deleted_user)
    rename_notes(username, new_deleted_user)
    rename_user_files(username, new_deleted_user)

    logger.info("Deleting account %s", username)
    current_user.remove()
    db.session.commit()
    logout_user()
    flash(gettext("Your account has successfully been deleted."), "success")
    return redirect(url_for("search.index"))


@settings.route('/change_email', methods=['POST'])
@check_permissions(login=True)
def change_email():
    form = EmailChangeForm(request.form)
    if form.validate_on_submit():
        new_email = request.form.get('email')
        if email_exists(new_email):
            flash(gettext("This email already exists."), "danger")
            return redirect(url_for("settings.index"))
        html = render_template("auth/email_change.html", new_email = new_email)
        if not send_email(current_user.email, "PeARS Instance - You requested an email change.", html):
            flash(gettext("Your email was changed, but we could not send a notification email."), "warning")
        current_user.email = new_email
        db.session.commit()
        flash(gettext("Your email has been successfully modified."), "success")
        return redirect(url_for("settings.index"))
    logger.debug("%s", form.errors)
    return redirect(url_for("settings.index"))


@settings.route('/change_username', methods=['POST'])
@check_permissions(login=True)
def change_username():
    username = current_user.username
    form = UsernameChangeForm(request.form)
    if form.validate_on_submit():
        new_username = request.form.get('username')
        if username_exists(new_username):
            flash(gettext("This username already exists."), "danger")
            return redirect(url_for("settings.index"))
        html = render_template("auth/username_change.html", new_username = new_username)
        if not send_email(current_user.email, "PeARS Instance - You requested a username change.", html):
            flash(gettext("Your username was changed, but we could not send a notification email."), "warning")
        rename_notes(username, new_username)
        rename_user_files(username, new_username)
        current_user.username = new_username
        db.session.commit()
        flash(gettext("Your username has been successfully modified."), "success")
        return redirect(url_for("settings.index"))
    logger.debug("%s", form.errors)
    return redirect(url_for("settings.index"))
