# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
# Import flask dependencies
from flask import Blueprint, request, render_template, send_from_directory, flash, redirect, url_for
from flask_login import current_user
from flask_babel import gettext
from os.path import dirname, realpath, join
from app.api.models import Urls, Pods
from app.utils_db import mv_pod
from flask import current_app
from app.extensions import db
from app.orchard.mk_urls_file import get_url_list_for_users
from app.auth.decorators import check_permissions
from app.auth.token import send_email
from app.auth.captcha import mk_captcha, check_captcha
from app.forms import ReportingForm, AnnotationForm, FeedbackForm

dir_path = dirname(dirname(realpath(__file__)))
logger = logging.getLogger(__name__)

# Define the blueprint:
orchard = Blueprint('orchard', __name__, url_prefix='/orchard')

@orchard.route('/')
@orchard.route('/index', methods=['GET', 'POST'])
def index():
    #query = db.session.query(Urls.pod.distinct().label("pod"))
    #keywords = [row.pod for row in query.all()]
    pods = db.session.query(Pods).all()
    themes = [p.name.split('.u.')[0] for p in pods]
    pod_urls = [p.url for p in pods]
    pears = []
    recorded = []
    for i in range(len(themes)):
        theme = themes[i]
        pod_sig = ''.join([char for char in pod_urls[i] if char.isalpha()]) #Make signature from pod url for collapse function
        if theme in recorded: #don't record same theme several times
            continue
        urls = []
        for u in Urls.query.filter(Urls.pod.contains(theme+'.u.')).all():
            if u.pod.startswith(theme+'.u.'):
                urls.append(u)
        pear = [theme, len(urls), pod_sig]
        pears.append(pear)
        recorded.append(theme) 
    return render_template('orchard/index.html', pears=pears)


@orchard.route('/get-a-pod', methods=['POST', 'GET'])
def get_a_pod():
    query = request.args.get('pod')
    filename, urls = get_url_list_for_users(query)
    logger.info("get_a_pod: generated %s", filename)
    return render_template('orchard/get-a-pod.html', urls=urls, query=query, location=filename)

@orchard.route("/download", methods=['GET'])
@check_permissions(login=True, confirmed=True, admin=True)
def download_file():
    filename = request.args.get('filename')
    logger.info("download_file: %s", filename)
    return send_from_directory(join(dir_path,'pods'), filename, as_attachment=True)


@orchard.route("/rename", methods=['GET'])
@check_permissions(login=True, confirmed=True, admin=True)
def rename_pod():
    podname = request.args.get('oldname')
    newname = request.args.get('newname')
    username = current_user.username
    message = mv_pod(podname, newname, username)
    flash(message, "success")
    return redirect(url_for('orchard.index'))


@orchard.route("/report", methods=['GET','POST'])
def report():
    is_logged_in = current_user.is_authenticated and current_user.is_confirmed
    email = current_user.email if is_logged_in else None
    form = ReportingForm()

    if request.method == 'GET':
        form.url.data = request.args.get('url')
        if not is_logged_in:
            captcha_id, _ = mk_captcha()
            form.captcha_id.data = captcha_id

    if form.validate_on_submit():
        # Verify captcha for logged-out users
        if not is_logged_in:
            captcha_id = request.form.get('captcha_id')
            captcha_answer = request.form.get('captcha_answer')
            if not check_captcha(captcha_id, captcha_answer):
                flash(gettext("Incorrect captcha. Please try again."), "warning")
                captcha_id, _ = mk_captcha()
                form.captcha_id.data = captcha_id
                return render_template('orchard/report.html', form=form, email=email)

        url = request.form.get('url')
        user_report = request.form.get('report')
        reporter = email if email else 'anonymous'
        mail_address = current_app.config['MAIL_USERNAME']
        if send_email(mail_address, 'URL report', 'Report from user ' + reporter + '<br>' + url + '<br>' + user_report):
            flash(gettext("Your report has been sent. Thank you!"), "success")
        else:
            flash(gettext("We could not send your report. Please try again later or contact the administrator."), "danger")
        return redirect(request.referrer or url_for('search.index'))
    return render_template('orchard/report.html', form=form, email=email)



@orchard.route("/feedback", methods=['GET','POST'])
@check_permissions(login=True, confirmed=True)
def feedback():
    username = current_user.username
    email = current_user.email
    form = FeedbackForm()
    if form.validate_on_submit():
        user_report = request.form.get('report')
        logger.debug("%s", user_report)
        mail_address = current_app.config['MAIL_USERNAME']
        if send_email(mail_address,'Feedback report', 'Feedback from user '+email+'<br>'+user_report):
            flash(gettext("Your feedback has been sent. Thank you!"), "success")
        else:
            flash(gettext("We could not send your feedback. Please try again later or contact the administrator."), "danger")
        return redirect(request.referrer or url_for('search.index'))
    return render_template('orchard/feedback.html', form=form, email=email)



@orchard.route("/annotate", methods=['GET','POST'])
@check_permissions(login=True, confirmed=True)
def annotate():
    username = current_user.username
    form = AnnotationForm()
    if request.method == 'GET':
        form.url.data=request.args.get('url')
    if form.validate_on_submit():
        url = request.form.get('url')
        note = request.form.get('note')
        logger.debug("%s %s", url, note)
        u = db.session.query(Urls).filter_by(url=url).first()
        note = '@'+username+' >> '+note
        if u.notes is not None:
            u.notes = u.notes+'<br>'+note
        else:
            u.notes = note
        db.session.add(u)
        db.session.commit()
        flash(gettext("Your note has been saved. Thank you!"), "success")
        return redirect(request.referrer or url_for('search.index'))
    return render_template('orchard/annotate.html', form=form)
