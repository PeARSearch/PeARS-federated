# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
from flask import Blueprint, render_template, request

from app.api.models import Pods
from app import app, OWN_BRAND

# Define the blueprint:
pages = Blueprint('pages', __name__, url_prefix='')

@pages.context_processor
def inject_brand():
    return dict(own_brand=OWN_BRAND)


@pages.route('/faq/')
def return_faq():
    siteurl = request.host_url
    sitename = app.config["SITENAME"]
    topic = app.config["SITE_TOPIC"]
    return render_template("pages/faq.html", sitename=sitename, siteurl=siteurl, topic=topic)


@pages.route('/acknowledgements/')
def return_acknowledgements():
    return render_template("pages/acknowledgements.html")

@pages.route('/privacy/')
def return_privacy():
    sitename = app.config["SITENAME"]
    return render_template("pages/privacy.html", sitename=sitename)

@pages.route('/terms-of-service/')
def return_tos():
    sitename = app.config["SITENAME"]
    return render_template("pages/tos.html", sitename=sitename)

@pages.route('/contact/')
def return_contact():
    sitename = app.config["SITENAME"]
    email = app.config["MAIL_DEFAULT_SENDER"].replace('@',' AT ')
    return render_template("pages/contact.html", email=email)


@pages.route('/maintenance/')
def return_maintenance():
    return render_template("pages/maintenance.html")

