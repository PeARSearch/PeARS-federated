# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
from flask import Blueprint, render_template, request

from app.api.models import Pods, Personalization
from flask import current_app
from app.extensions import db

# Define the blueprint:
pages = Blueprint('pages', __name__, url_prefix='')


@pages.route('/faq/')
def return_faq():
    siteurl = request.host_url
    sitename = current_app.config["SITENAME"]
    topic = current_app.config["SITE_TOPIC"]
    return render_template("pages/faq.html", sitename=sitename, siteurl=siteurl, topic=topic)

@pages.route('/licenses/')
def return_licenses():
    return render_template("pages/licenses.html")


@pages.route('/acknowledgements/')
def return_acknowledgements():
    acknowledgements = []
    acks = db.session.query(Personalization).filter_by(feature='thanks').all()
    if acks:
        for ack in acks:
            acknowledgements.append(ack.text)
    return render_template("pages/acknowledgements.html", acknowledgements=acknowledgements)

@pages.route('/privacy/')
def return_privacy():
    sitename = current_app.config["SITENAME"]
    orgname = current_app.config["ORG_NAME"]
    address = current_app.config["ORG_ADDRESS"]
    email = current_app.config["ORG_EMAIL"]
    servers = current_app.config["SERVERS"]
    return render_template("pages/privacy.html", sitename=sitename, orgname=orgname, address=address, email=email, servers=servers)

@pages.route('/terms-of-service/')
def return_tos():
    applicable_law = current_app.config["APPLICABLE_LAW"]
    sitename = current_app.config["SITENAME"]
    orgname = current_app.config["ORG_NAME"]
    address = current_app.config["ORG_ADDRESS"]
    email = current_app.config["ORG_EMAIL"]
    return render_template("pages/tos.html", applicable_law=applicable_law, sitename=sitename, orgname=orgname, address=address, email=email)

@pages.route('/impressum/')
def return_contact():
    sitename = current_app.config["SITENAME"]
    orgname = current_app.config["ORG_NAME"]
    address = current_app.config["ORG_ADDRESS"]
    email = current_app.config["ORG_EMAIL"]
    eu = current_app.config["EU_SPECIFIC"]
    tax_office = current_app.config["TAX_OFFICE"]
    registration_number = current_app.config["REGISTRATION_NUMBER"]
    vat_number = current_app.config["VAT_NUMBER"]
    return render_template("pages/contact.html", email=email, orgname=orgname, address=address, eu=eu, \
            tax_office=tax_office, registration_number=registration_number, vat_number=vat_number)


@pages.route('/maintenance/')
def return_maintenance():
    return render_template("pages/maintenance.html")

