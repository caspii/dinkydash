"""
Authentication forms for registration and login.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from dinkydash.models import User


class RegistrationForm(FlaskForm):
    """Form for user registration."""

    family_name = StringField(
        'Family Name',
        validators=[
            DataRequired(message='Family name is required'),
            Length(min=2, max=100, message='Family name must be between 2 and 100 characters')
        ],
        render_kw={'placeholder': 'The Smith Family'}
    )

    email = StringField(
        'Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Invalid email address'),
            Length(max=255)
        ],
        render_kw={'placeholder': 'you@example.com'}
    )

    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message='Password is required'),
            Length(min=8, max=128, message='Password must be at least 8 characters')
        ],
        render_kw={'placeholder': 'Minimum 8 characters'}
    )

    confirm_password = PasswordField(
        'Confirm Password',
        validators=[
            DataRequired(message='Please confirm your password'),
            EqualTo('password', message='Passwords must match')
        ],
        render_kw={'placeholder': 'Re-enter password'}
    )

    submit = SubmitField('Create Account')

    def validate_email(self, email):
        """Check if email is already registered."""
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError('This email is already registered. Please log in or use a different email.')


class LoginForm(FlaskForm):
    """Form for user login."""

    email = StringField(
        'Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Invalid email address')
        ],
        render_kw={'placeholder': 'you@example.com'}
    )

    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message='Password is required')
        ],
        render_kw={'placeholder': 'Your password'}
    )

    submit = SubmitField('Log In')
