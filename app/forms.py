from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, TextField, PasswordField
from wtforms.validators import Length, DataRequired, EqualTo, Email

class RegistrationForm(FlaskForm):
    username = TextField('Username', [Length(min=4, max=25, message="Your username should have between 4 and 25 characters.")])
    email = StringField('Email Address', [DataRequired(), Email()])
    password = PasswordField('New Password', [DataRequired(), Length(min=6, max=20, message="Your password should have between 6 and 20 characters."), EqualTo('confirm', message='Passwords must match')])
    confirm = PasswordField('Repeat Password')
    accept_tos = BooleanField('I accept the TOS and Privacy statement', [DataRequired()])

class LoginForm(FlaskForm):
    email = StringField('Email Address', [DataRequired(), Email()])
    password = PasswordField('Password', [DataRequired(), Length(min=6, max=20, message="Your password should have between 6 and 20 characters.")])

class PasswordForgottenForm(FlaskForm):
    email = StringField('Email Address', [DataRequired(), Email()])

class PasswordChangeForm(FlaskForm):
    password = PasswordField('New Password', [DataRequired(), Length(min=6, max=20, message="Your password should have between 6 and 20 characters."), EqualTo('confirm', message='Passwords must match')])
    confirm = PasswordField('Repeat Password')

