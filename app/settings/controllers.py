# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


# Import flask dependencies
import logging
from app import db, OWN_BRAND
from app.api.models import Urls

from app.forms import ManualEntryForm
from flask import Blueprint, flash, request, render_template, Response
from flask_login import current_user


# Define the blueprint:
settings = Blueprint('settings', __name__, url_prefix='/settings')

@settings.context_processor
def inject_brand():
    return dict(own_brand=OWN_BRAND)


# Set the route and accepted methods
@settings.route("/")
def index():
    username = current_user.username
    email = current_user.email
    form = ManualEntryForm()
    contributions = []
    for i in db.session.query(Urls).filter_by(contributor='@'+username).all():
        contributions.append([i.url, i.title])
    num_contributions = len(contributions)

    return render_template("settings/index.html", username=username, email=email, num_contributions=num_contributions, contributions=contributions, form=form)

