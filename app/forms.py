from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, TextAreaField, PasswordField, HiddenField, URLField
from wtforms.validators import Length, DataRequired, InputRequired, EqualTo, Email, URL
from flask_babel import lazy_gettext

class SearchForm(FlaskForm):
    query = StringField("", [DataRequired()])

class RegistrationForm(FlaskForm):
    username = StringField(lazy_gettext('Username'), [Length(min=4, max=25, message=lazy_gettext("Your username should have between 4 and 25 characters."))])
    email = StringField(lazy_gettext('Email Address'), [DataRequired(), Email()])
    password = PasswordField(lazy_gettext('New Password'), [DataRequired(), Length(min=6, max=20, message=lazy_gettext("Your password should have between 6 and 20 characters.")), EqualTo('confirm', message=lazy_gettext('Passwords must match'))])
    confirm = PasswordField(lazy_gettext('Repeat Password'))
    captcha = HiddenField()
    captcha_answer = StringField('', [DataRequired()])
    accept_tos = BooleanField(lazy_gettext('I accept the TOS and Privacy statement'), [DataRequired()])

class LoginForm(FlaskForm):
    email = StringField(lazy_gettext('Email Address'), [DataRequired(), Email()])
    password = PasswordField(lazy_gettext('Password'), [DataRequired(), Length(min=6, max=20, message=lazy_gettext("Your password should have between 6 and 20 characters."))])

class PasswordForgottenForm(FlaskForm):
    email = StringField(lazy_gettext('Email Address'), [DataRequired(), Email()])

class PasswordChangeForm(FlaskForm):
    password = PasswordField(lazy_gettext('New Password'), [DataRequired(), Length(min=6, max=20, message=lazy_gettext("Your password should have between 6 and 20 characters.")), EqualTo('confirm', message=lazy_gettext('Passwords must match'))])
    confirm = PasswordField(lazy_gettext('Repeat Password'))

class EmailChangeForm(FlaskForm):
    email = StringField(lazy_gettext('New Email'), [DataRequired(), Email()])

class UsernameChangeForm(FlaskForm):
    username = StringField(lazy_gettext('New Username'), [Length(min=4, max=25, message=lazy_gettext("Your username should have between 4 and 25 characters."))])

class IndexerForm(FlaskForm):
    suggested_url = URLField(lazy_gettext('The url to index'), [DataRequired(), URL()], render_kw={"placeholder": lazy_gettext("The URL you would like to index.")})
    theme = StringField(lazy_gettext('Theme'), [DataRequired(), Length(max=50)],  render_kw={"placeholder": lazy_gettext("A category for your URL. Start typing and suggestions will appear, but you can also write your own.")})
    note = StringField(lazy_gettext('Optional note*'), [Length(max=100)],  render_kw={"placeholder": lazy_gettext("Anything extra you would like people to know about this resource.")})
    accept_tos = BooleanField(lazy_gettext('I confirm that my suggestion does not contravene the Terms of Service'), [DataRequired()])

class ManualEntryForm(FlaskForm):
    title = StringField(lazy_gettext('A title for your entry'), [DataRequired(), Length(min=8, max=100, message=lazy_gettext("The title of your entry should have between 4 and 100 characters."))])
    description = TextAreaField(lazy_gettext('Description'), [DataRequired(), Length(max=500)])
    accept_tos = BooleanField(lazy_gettext('I confirm that my entry does not contravene the Terms of Service'), [DataRequired()])

class ReportingForm(FlaskForm):
    url = StringField(lazy_gettext('The url you are reporting'), [DataRequired(), URL()])
    report = TextAreaField(lazy_gettext('Description of the issue'), [DataRequired(), Length(max=300)])
    accept_tos = BooleanField(lazy_gettext('I confirm that I may be contacted in relation to my report.'), [DataRequired()])

class FeedbackForm(FlaskForm):
    report = TextAreaField(lazy_gettext('Your feedback'), [DataRequired(), Length(max=1000)])
    accept_tos = BooleanField(lazy_gettext('I confirm that I may be contacted in relation to my report.'), [DataRequired()])

class AnnotationForm(FlaskForm):
    url = StringField(lazy_gettext('The url you wish to annotate'), [DataRequired(), URL()])
    note = TextAreaField(lazy_gettext('Your note'), [DataRequired(), Length(max=300)])
    accept_tos = BooleanField(lazy_gettext('I confirm that my comment can be openly published.'), [DataRequired()])
