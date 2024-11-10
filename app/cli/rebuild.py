# Scripts to rebuild a database and pods from backups
from os.path import join
import joblib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.sparse import vstack, load_npz, save_npz, csr_matrix
from sqlalchemy import create_engine
from app import db, VEC_SIZE
from app.api.models import User, Personalization
from app.utils_db import create_or_replace_url_in_db, create_pod_in_db, create_pod_npz_pos

def rebuild_personalization(basedir):
    source_db = 'sqlite:///' + join(basedir, 'app.db')
    cnx = create_engine(source_db).connect()
    df = pd.read_sql_table('personalization', cnx)
    for _, f in df.iterrows():
        feature = f['feature']
        text = f['text']
        language = f['language']
        feature = Personalization(feature=feature, text=text, language=language)
        db.session.add(feature)
        db.session.commit()

def rebuild_users(basedir):
    source_db = 'sqlite:///' + join(basedir, 'app.db')
    cnx = create_engine(source_db).connect()
    df = pd.read_sql_table('user', cnx)
    for _, u in df.iterrows():
        print(u['username'])
        username = u['username']
        email = u['email']
        is_admin = u['is_admin']
        user = User(username=username, email=email, is_admin=is_admin)
        try:
            confirmed_on = u['confirmed_on']
            password = u['password']
            user.password = password
            user.is_confirmed=True
            user.confirmed_on=confirmed_on
        except:
            print("Issue with confirmation date of user", username)
        db.session.add(user)
        db.session.commit()

def rebuild_pods_and_urls(pod_dir, basedir):
    source_db = 'sqlite:///' + join(basedir, 'app.db')
    source_pod_dir = join(basedir, 'pods')
    cnx = create_engine(source_db).connect()
    df = pd.read_sql_table('pods', cnx)
    for _, p in df.iterrows():
        print(f"\n\n POD {p['name']}")
        dfu = pd.read_sql_table('urls', cnx)
        urls = dfu.loc[dfu['pod'] == p['name']]
        theme = p['name'].split('.u.')[0]
        username = p['name'].split('.u.')[1]
        lang = p['language']
        try:
            idx_path = join(source_pod_dir, username, username+'.idx')
            idx_to_url = joblib.load(idx_path)
            print(">> Shape idx to url:", len(idx_to_url))
        except:
            continue
        
        try:
            npz_idx_path = join(source_pod_dir, username, lang, p['name']+'.npz.idx')
            npz_to_idx = joblib.load(npz_idx_path)
            print(">> Shape npz to idx:", len(idx_to_url))
        except:
            continue

        try:
            npz_path = join(source_pod_dir, username, lang, p['name']+'.npz')
            npz = load_npz(npz_path).toarray()
            print(">> Shape npz:", npz.shape)
        except:
            continue

        user_dir = join(pod_dir, username, lang)
        Path(user_dir).mkdir(parents=True, exist_ok=True)
        create_pod_in_db(username, theme, lang)
        new_npz_path = join(pod_dir, username, lang, p['name']+'.npz')
        m = np.zeros((1,VEC_SIZE))
        m = csr_matrix(m)
        
        for _, url in urls.iterrows():
            try:
                k = idx_to_url[1].index(url['url'])
                idx = idx_to_url[0][k]
                k = npz_to_idx[1].index(idx)
                row = npz_to_idx[0][k]
                v = npz[row]
                m = vstack((m,v))
                vector = m.shape[0]-1
                notes = ''
                if url['notes']:
                    notes = url['notes']
                create_or_replace_url_in_db(url['url'], url['title'], vector, url['snippet'], theme, lang, notes, url['share'], url['contributor'], url['doctype'])
            except:
                    print(">> CLI:REBUILD DB: Problem with url",url['url'])
        save_npz(new_npz_path, m)

