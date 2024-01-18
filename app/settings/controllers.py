# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


# Import flask dependencies
import logging
from app import OWN_BRAND

from flask import (Blueprint,
                   flash,
                   request,
                   render_template,
                   Response)


# Define the blueprint:
settings = Blueprint('settings', __name__, url_prefix='/settings')

@settings.context_processor
def inject_brand():
    return dict(own_brand=OWN_BRAND)


# Set the route and accepted methods
@settings.route("/")
def index():
    return render_template("settings/index.html")


