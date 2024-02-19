# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


# Import flask dependencies
import logging
from app import db, OWN_BRAND
from app.api.models import Urls
from app.forms import ManualEntryForm
from app.api.controllers import return_url_delete

from flask import Blueprint, flash, request, render_template, redirect, url_for
from flask_login import login_required, current_user
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
    for i in db.session.query(Urls).filter_by(contributor='@'+username).all():
        contributions.append([i.url, i.title])
    contributions = contributions[::-1] #reverse from most recent
    num_contributions = len(contributions)

    return render_template("settings/index.html", username=username, email=email, num_contributions=num_contributions, contributions=contributions, form=form)

@settings.route('/delete', methods=['GET'])
@login_required
@check_is_confirmed
def delete_url():
    username = current_user.username
    url = request.args.get('url')
    pod = db.session.query(Urls).filter_by(url=url).first().pod
    # Double check url belongs to the user
    contributor = pod.split('.u.')[1]
    if contributor != username:
        flash("URL does not belong to you and cannot be deleted.")
        return redirect(url_for("settings.index"))
    try:
        return_url_delete(url)
        flash("URL "+url+" was successfully deleted.")
    except:
        flash("There was a problem deleting URL "+url+" Please contact your administrator.")
    return redirect(url_for("settings.index"))
