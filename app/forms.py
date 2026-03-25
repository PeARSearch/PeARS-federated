from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, TextAreaField, PasswordField, HiddenField, URLField
from wtforms.validators import Length, Optional, DataRequired, InputRequired, EqualTo, Email, URL, ValidationError
from flask_babel import lazy_gettext


class URL_or_pearslocal(URL):
    """
    Validator that accepts real URLs as well as pearslocal strings
    """
    def __init__(self, *args):
        super().__init__(*args)

    def __call__(self, form, field):
        data = field.data or ""
        if data.startswith("pearslocal"):
            return
        super().__call__(form, field)


class SearchForm(FlaskForm):
    query = StringField("", [DataRequired()])

class RegistrationForm(FlaskForm):
    username = StringField(lazy_gettext('Username'), [Length(min=4, max=25, message=lazy_gettext("Your username should have between 4 and 25 characters."))])
    email = StringField(lazy_gettext('Email Address'), [DataRequired(), Email()])
    password = PasswordField(lazy_gettext('New Password'), [DataRequired(), Length(min=6, max=20, message=lazy_gettext("Your password should have between 6 and 20 characters.")), EqualTo('confirm', message=lazy_gettext('Passwords must match'))])
    confirm = PasswordField(lazy_gettext('Repeat Password'))
    captcha_id = HiddenField()
    captcha_answer = StringField(lazy_gettext("Captcha:"), [DataRequired()])
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
    suggested_url = URLField(lazy_gettext('URL to index'), [DataRequired(), URL()], render_kw={"placeholder": lazy_gettext("https://example.com/article")})
    theme = StringField(lazy_gettext('Category'), [DataRequired(), Length(max=50)],  render_kw={"placeholder": lazy_gettext("Start typing — suggestions will appear, or create your own")})
    note = TextAreaField(lazy_gettext('Note (optional)'), [Length(max=1000)],  render_kw={"placeholder": lazy_gettext("Anything extra you would like people to know about this resource. (Max 1000 characters.)"), "rows": "3"})
    accept_tos = BooleanField(lazy_gettext('I confirm that my suggestion does not contravene the Terms of Service'), [DataRequired()])

class SuggestionForm(FlaskForm):
    suggested_url = URLField(lazy_gettext('URL to suggest'), [DataRequired(), URL()], render_kw={"placeholder": lazy_gettext("https://example.com/article")})
    theme = StringField(lazy_gettext('Category'), [DataRequired(), Length(max=50)],  render_kw={"placeholder": lazy_gettext("Start typing — suggestions will appear, or create your own")})
    note = TextAreaField(lazy_gettext('Note (optional)'), [Length(max=1000)],  render_kw={"placeholder": lazy_gettext("Anything extra you would like people to know about this resource. (Max 1000 characters.)"), "rows": "3"})
    captcha_id = HiddenField()
    captcha_answer = StringField(lazy_gettext("Captcha:"), [DataRequired()])

class ManualEntryForm(FlaskForm):
    title = StringField(lazy_gettext('Title'), [DataRequired(), Length(min=8, max=100, message=lazy_gettext("The title should have between 8 and 100 characters."))], render_kw={"placeholder": lazy_gettext("A descriptive title for your entry")})
    related_url = URLField(lazy_gettext('Related URL (optional)'), [Optional(), URL()], render_kw={"placeholder": lazy_gettext("https://example.com — entry will link to this URL")})
    description = TextAreaField(lazy_gettext('Description'), [DataRequired(), Length(max=1000)],  render_kw={"placeholder": lazy_gettext("What is this resource about? (Max 1000 characters.)"), "rows": "3"})
    accept_tos = BooleanField(lazy_gettext('I confirm that my entry does not contravene the Terms of Service'), [DataRequired()])

class ReportingForm(FlaskForm):
    url = StringField(lazy_gettext('The url you are reporting'), [DataRequired(), URL_or_pearslocal()])
    report = TextAreaField(lazy_gettext('Description of the issue'), [DataRequired(), Length(max=1000)],  render_kw={"placeholder": lazy_gettext("Max 1000 characters.")})
    accept_tos = BooleanField(lazy_gettext('I confirm that I may be contacted in relation to my report.'), [DataRequired()])
    captcha_id = HiddenField()
    captcha_answer = StringField(lazy_gettext("Captcha:"))

class FeedbackForm(FlaskForm):
    report = TextAreaField(lazy_gettext('Your feedback'), [DataRequired(), Length(max=1000)],  render_kw={"placeholder": lazy_gettext("Max 1000 characters.")})
    accept_tos = BooleanField(lazy_gettext('I confirm that I may be contacted in relation to my report.'), [DataRequired()])

class AnnotationForm(FlaskForm):
    url = StringField(lazy_gettext('The url you wish to annotate'), [DataRequired(), URL_or_pearslocal()])
    note = TextAreaField(lazy_gettext('Your note (max 1000 characters)'), [DataRequired(), Length(max=1000)])
    accept_tos = BooleanField(lazy_gettext('I confirm that my comment can be openly published.'), [DataRequired()])
