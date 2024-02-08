from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, TextField, TextAreaField, PasswordField
from wtforms.validators import Length, DataRequired, InputRequired, EqualTo, Email, url

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

class ManualEntryForm(FlaskForm):
    title = TextField('A title for your entry', [DataRequired(), Length(min=8, max=100, message="Your username should have between 4 and 100 characters.")])
    description = TextAreaField('Description', [DataRequired(), Length(max=200)])
    accept_tos = BooleanField('I confirm that my entry does not contravene the Terms of Service', [DataRequired()])

class ReportingForm(FlaskForm):
    url = StringField('The url you are reporting', [DataRequired(), url()])
    report = TextAreaField('Description of the issue', [DataRequired(), Length(max=300)])
    accept_tos = BooleanField('I confirm that I may be contacted in relation to my report.', [DataRequired()])

class AnnotationForm(FlaskForm):
    url = StringField('The url you wish to annotate', [DataRequired(), url()])
    note = TextAreaField('Your note', [DataRequired(), Length(max=300)])
    accept_tos = BooleanField('I confirm that my comment can be openly published.', [DataRequired()])
