# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
from flask import Blueprint, flash, request, render_template, Response
from os.path import dirname, realpath, join, isfile
from app import LANG, STOPWORDS, OWN_BRAND
from app.indexer.mk_page_vector import tokenize_text
from app.analysis.ds import analyse_ppmis 
from pathlib import Path
import joblib

app_dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(app_dir_path, 'pods')
analysis_dir = join(app_dir_path, 'analysis')
Path(analysis_dir).mkdir(exist_ok=True, parents=True)

# Define the blueprint:
analysis = Blueprint('analysis', __name__, url_prefix='/analysis')

@analysis.route('/')
@analysis.route('/index', methods=['GET', 'POST'])
def index():
    return render_template('analysis/index.html', own_brand=OWN_BRAND)

@analysis.route('/ppmi', methods=['GET', 'POST'])
def ppmi():
    ppmis = []
    ppmi_path = join(analysis_dir, 'ppmis.jbl')
    top_ppmis = analyse_ppmis(pod_dir)
    joblib.dump(top_ppmis, ppmi_path)
    flash("Analysis is finished. You can now search the results.", 'analysis')
    return render_template('analysis/index.html', own_brand=OWN_BRAND)

@analysis.route('/associate', methods=['GET'])
def search():
    query = request.args.get('q')
    query = ' '.join([w for w in query.split() if w not in STOPWORDS])
    query = tokenize_text(LANG, query).split()
    print(query)
    ppmis = []
    ppmi_path = join(analysis_dir, 'ppmis.jbl')
    if not isfile(ppmi_path):
        flash('Please first run the analyser.', 'association')
        return render_template('analysis/index.html', own_brand=OWN_BRAND)
    else:
        all_ppmis = joblib.load(ppmi_path)
        for token in query:
            if len(token) > 2 and token in all_ppmis:
                ppmis.append((token,' '.join([t for t in all_ppmis[token] if len(t) > 2])))
        if len(ppmis) == 0:
            flash('No analysis found for this word. This instance need more data on this topic.', 'association')
            return render_template('analysis/index.html')
    return render_template('analysis/index.html', ppmis=ppmis, own_brand=OWN_BRAND)

