# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


# Import flask dependencies
import logging
from os.path import join
from flask import Blueprint, flash, request, render_template, redirect, url_for
from flask_login import login_required, current_user
from app import db, OWN_BRAND
from app.api.models import Urls
from app.forms import ManualEntryForm
from app.api.controllers import return_url_delete
from app.utils_db import delete_url_representations
from app.auth.decorators import check_is_confirmed


# Define the blueprint:
settings = Blueprint('settings', __name__, url_prefix='/settings')

@settings.context_processor
def inject_brand():
    return dict(own_brand=OWN_BRAND)


# Set the route and accepted methods
@settings.route("/")
@login_required
def index():
    username = current_user.username
    email = current_user.email
    form = ManualEntryForm()
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
        print("NOTES",notes)
        note = ' | '.join(notes)
        comments.append([url, note])
    return render_template("settings/index.html", username=username, email=email, num_contributions=num_contributions, contributions=contributions, tips=tips, comments=comments, form=form)

@settings.route('/delete', methods=['GET'])
@login_required
@check_is_confirmed
def delete_url():
    username = current_user.username
    url = request.args.get('url').split('get?url=')[1]
    pod = db.session.query(Urls).filter_by(url=url).first().pod
    # Double check url belongs to the user
    contributor = pod.split('.u.')[1]
    if contributor != username:
        flash("URL does not belong to you and cannot be deleted.")
        return redirect(url_for("settings.index"))
    try:
        delete_url_representations(url)
        flash("URL "+url+" was successfully deleted.")
    except:
        flash("There was a problem deleting URL "+url+" Please contact your administrator.")
    return redirect(url_for("settings.index"))

@settings.route('/delcomment', methods=['GET'])
@login_required
@check_is_confirmed
def delete_comment():
    username = current_user.username
    u = request.args.get('url').split('get?url=')[1]
    url = db.session.query(Urls).filter_by(url=u).first()
    notes = ['@'+note for note in url.notes.split('@') if not note.startswith(username)]
    notes = [note for note in notes if note !='@']
    print("NOTES",notes)
    if len(notes) > 0:
        url.notes = '<br>'.join(notes)
    else:
        url.notes = None
    db.session.commit()
    flash("Your comments for "+u+" were successfully deleted.")
    return redirect(url_for("settings.index"))
