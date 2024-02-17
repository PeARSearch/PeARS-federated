# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
from flask import Blueprint, request, render_template, Response
from os.path import dirname, realpath, join
from app.analysis.ds import analyse_ppmis 

dir_path = dirname(dirname(dirname(realpath(__file__))))
pod_dir = join(dir_path, 'app', 'static', 'pods')

# Define the blueprint:
analysis = Blueprint('analysis', __name__, url_prefix='/analysis')

@analysis.route('/')
@analysis.route('/index', methods=['GET', 'POST'])
def index():
    return render_template('analysis/index.html', ppmis=[])

def ppmi():
    top_ppmis = analyse_ppmis(pod_dir)
    ppmis = []
    for k,v in top_ppmis.items():
        ppmis.append((k,' '.join([t for t in v if len(t) > 2])))
    return render_template('analysis/index.html', ppmis=ppmis)

