# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from app import db
from flask_login import UserMixin
import numpy as np
import configparser
import joblib
from glob import glob
from os.path import join, isdir, exists, dirname, realpath
import sentencepiece as spm

sp = spm.SentencePieceProcessor()

def get_installed_languages():
    dir_path = dirname(dirname(realpath(__file__)))
    print('PATH',dir_path)
    installed_languages = []
    spm_dir = ''
    language_paths = glob(join(dir_path,'api/models/*/'))
    for p in language_paths:
        lang = p[:-1].split('/')[-1]
        installed_languages.append(lang)
    print("Installed languages:",installed_languages)
    return installed_languages

installed_languages = get_installed_languages()


# Define a base model for other database tables to inherit
class Base(db.Model):

    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    date_created = db.Column(db.DateTime, default=db.func.current_timestamp())
    date_modified = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp())


class AccessLogs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    log_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_logged_in = db.Column(db.Boolean)
    user_id = db.Column(db.Integer)
    user_email = db.Column(db.String(1000))
    user_is_confirmed = db.Column(db.Boolean)
    user_is_admin = db.Column(db.Boolean)
    event_type = db.Column(db.String(1000))
    endpoint = db.Column(db.String(1000))
    requested_url = db.Column(db.String(1000))
    response_code = db.Column(db.Integer)
    messages = db.Column(db.String(1000))

    def __init__(
        self, 
        logged_in, 
        user_id, 
        user_is_confirmed, 
        user_is_admin, 
        user_email, 
        event_type, 
        endpoint, 
        requested_url, 
        response_code, 
        messages
    ):
        self.user_logged_in = logged_in
        self.user_id = user_id
        self.user_email = user_email
        self.user_is_confirmed = user_is_confirmed
        self.user_is_admin = user_is_admin
        self.event_type = event_type
        self.endpoint = endpoint
        self.requested_url = requested_url
        self.response_code = response_code
        self.messages = messages

    @property
    def serialize(self):
        return {
            "id": self.id,
            "log_date": self.log_date,
            "logged_in": self.logged_in,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "event_type": self.event_type,
            "endpoint": self.endpoint,
            "requested_url": self.requested_url,
            "response_code": self.response_code,
            "messages": self.messages
        }


class Suggestions(Base):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(1000))
    pod = db.Column(db.String(1000))
    notes = db.Column(db.String(1000))
    contributor = db.Column(db.String(1000))

    def __init__(self, url=None, pod=None, notes=None, contributor=None):
        self.url = url
        self.pod = pod
        self.notes = notes
        self.contributor = contributor

    def __repr__(self):
        return self.url

    @property
    def serialize(self):
        return {
            'id': self.id,
            'pod': self.pod,
            'notes': self.notes,
            'contributor': self.contributor
        }

    def as_dict(self):
        return {c.name: str(getattr(self, c.name)) for c in self.__table__.columns}


class Urls(Base):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(1000))
    title = db.Column(db.String(1000))
    snippet = db.Column(db.String(1000))
    doctype = db.Column(db.String(1000))
    vector = db.Column(db.Integer)
    pod = db.Column(db.String(1000))
    notes = db.Column(db.String(1000))
    img = db.Column(db.String(1000))
    share = db.Column(db.String(1000))
    contributor = db.Column(db.String(1000))

    def __init__(self,
                 url=None,
                 title=None,
                 snippet=None,
                 doctype=None,
                 vector=None,
                 pod=None,
                 notes=None,
                 img=None,
                 share=None,
                 contributor=None):
        self.url = url
        self.title = title
        self.snippet = snippet
        self.doctype = doctype
        self.vector = vector
        self.pod = pod
        self.notes = notes
        self.img = img
        self.share = share
        self.contributor = contributor

    def __repr__(self):
        return self.url

    @property
    def serialize(self):
        return {
            'id': self.id,
            'url': self.url,
            'title': self.title,
            'snippet': self.snippet,
            'doctype': self.doctype,
            'vector': self.vector,
            'pod': self.pod,
            'notes': self.notes,
            'img': self.img,
            'share': self.share,
            'contributor': self.contributor
        }

    def as_dict(self):
        return {c.name: str(getattr(self, c.name)) for c in self.__table__.columns}


class Pods(Base):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1000))
    url = db.Column(db.String(1000))
    description = db.Column(db.String(7000))
    language = db.Column(db.String(1000))
    DS_vector = db.Column(db.String(7000))
    word_vector = db.Column(db.String(7000))
    registered = db.Column(db.Boolean)

    def __init__(self,
                 name=None,
                 url=None,
                 description=None,
                 language=None,
                 DS_vector=None,
                 word_vector=None,
                 registered=False):
        self.name = name
        self.url = url
        self.description = description
        self.language = language

    @property
    def serialize(self):
        return {
            'name': self.name,
            'url': self.url,
            'description': self.description,
            'language': self.language,
            'DSvector': self.DS_vector,
            'wordvector': self.word_vector,
            'registered': self.registered
        }



class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    username = db.Column(db.String(1000))
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    confirmed_on = db.Column(db.DateTime, nullable=True)
    
    def __init__(self,
                 email=None,
                 password=None,
                 username=None,
                 is_admin=False,
                 is_confirmed=False,
                 confirmed_on=None):
        self.email = email
        self.password = password
        self.username = username
        self.is_admin = is_admin
        self.is_confirmed = is_confirmed
        self.confirmed_on = confirmed_on

    @property
    def serialize(self):
        return {
            'email': self.email,
            'password': self.password,
            'username': self.username,
            'is_admin': self.is_admin,
            'is_confirmed': self.is_confirmed,
            'confirmed_on': self.confirmed_on
        }
    def remove(self):
        db.session.delete(self)


class Personalization(Base):
    id = db.Column(db.Integer, primary_key=True)
    feature = db.Column(db.String(1000))
    text = db.Column(db.String(7000))
    language = db.Column(db.String(10))

    def __init__(self,
                 feature=None,
                 text=None,
                 language=None):
        self.feature = feature
        self.text = text
        self.language = language
