# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
from flask import Blueprint, request, render_template, send_from_directory, flash
from flask_login import login_required, current_user
from os.path import dirname, realpath, join
from app.api.models import Urls, Pods
from app import db, OWN_BRAND
from app.orchard.mk_urls_file import make_shareable_pod
from app.auth.decorators import check_is_confirmed
from app.auth.token import send_email
from app.forms import ReportingForm, AnnotationForm

dir_path = dirname(dirname(realpath(__file__)))

# Define the blueprint:
orchard = Blueprint('orchard', __name__, url_prefix='/orchard')

@orchard.context_processor
def inject_brand():
    return dict(own_brand=OWN_BRAND)


@orchard.route('/')
@orchard.route('/index', methods=['GET', 'POST'])
@login_required
@check_is_confirmed
def index():
    #query = db.session.query(Urls.pod.distinct().label("pod"))
    #keywords = [row.pod for row in query.all()]
    pods = db.session.query(Pods).all()
    themes = [p.name.split('.u.')[0] for p in pods]
    pears = []
    recorded = []
    for theme in themes:
        if theme in recorded: #don't record same theme several times
            continue
        pear_urls = []
        for u in Urls.query.filter(Urls.pod.contains(theme)).all():
            pear_urls.append(u)
        pear = [theme, len(pear_urls)]
        pears.append(pear)
        recorded.append(theme) 
    return render_template('orchard/index.html', pears=pears)


@orchard.route('/get-a-pod', methods=['POST', 'GET'])
@login_required
@check_is_confirmed
def get_a_pod():
    query = request.args.get('pod')
    filename, urls = make_shareable_pod(query)
    print("\t>> Orchard: get_a_pod: generated", filename)
    return render_template('orchard/get-a-pod.html', urls=urls, query=query, location=filename)

@orchard.route("/download", methods=['GET'])
@login_required
@check_is_confirmed
def download_file():
    filename = request.args.get('filename')
    print('>> orchard: download_file:',filename)
    return send_from_directory(join(dir_path,'static','pods'), filename, as_attachment=True)

@orchard.route("/report", methods=['GET','POST'])
@login_required
@check_is_confirmed
def report():
    username = current_user.username
    email = current_user.email
    form = ReportingForm()
    if request.method == 'GET':
        form.url.data=request.args.get('url')
    if form.validate_on_submit():
        url = request.form.get('url')
        report = request.form.get('report')
        print(url,report)
        send_email('aurelie@possible-worlds.xyz','URL report',url+'<br>'+report)
        flash("Your report has been sent. Thank you!", "success")
        return render_template('search/index.html')
    else:
        return render_template('orchard/report.html', form=form, email=email)

@orchard.route("/annotate", methods=['GET','POST'])
@login_required
@check_is_confirmed
def annotate():
    username = current_user.username
    form = AnnotationForm()
    if request.method == 'GET':
        form.url.data=request.args.get('url')
    if form.validate_on_submit():
        url = request.form.get('url')
        note = request.form.get('note')
        print(url,note)
        u = db.session.query(Urls).filter_by(url=url).first()
        note = '@'+username+' >> '+note
        if u.notes is not None:
            u.notes = u.notes+'<br>'+note
        else:
            u.notes = note
        db.session.add(u)
        db.session.commit()
        flash("Your note has been saved. Thank you!", "success")
        return render_template('search/index.html')
    else:
        return render_template('orchard/annotate.html', form=form)
