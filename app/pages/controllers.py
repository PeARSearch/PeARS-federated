# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
from flask import Blueprint, render_template

from app.api.models import Pods
from app import OWN_BRAND

# Define the blueprint:
pages = Blueprint('pages', __name__, url_prefix='')

@pages.context_processor
def inject_brand():
    return dict(own_brand=OWN_BRAND)


@pages.route('/faq/')
def return_faq():
    return render_template("pages/faq.html")


@pages.route('/acknowledgements/')
def return_acknowledgements():
    return render_template("pages/acknowledgements.html")

@pages.route('/privacy/')
def return_privacy():
    return render_template("pages/privacy.html")

@pages.route('/terms-of-service/')
def return_tos():
    return render_template("pages/tos.html")

@pages.route('/contact/')
def return_contact():
    return render_template("pages/contact.html")


@pages.route('/maintenance/')
def return_maintenance():
    return render_template("pages/maintenance.html")

