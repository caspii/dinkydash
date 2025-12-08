"""
Dashboard management forms.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, RadioField
from wtforms.validators import DataRequired, Length


class DashboardForm(FlaskForm):
    """Form for creating/editing dashboards."""
    
    name = StringField(
        'Dashboard Name',
        validators=[
            DataRequired(message='Dashboard name is required'),
            Length(min=1, max=100, message='Dashboard name must be between 1 and 100 characters')
        ],
        render_kw={'placeholder': 'e.g., Kitchen Dashboard', 'class': 'form-control'}
    )
    
    layout_size = RadioField(
        'Layout Size',
        choices=[
            ('small', 'Small - Compact view for small screens'),
            ('medium', 'Medium - Default size for most screens'),
            ('large', 'Large - Big view for TVs and large displays')
        ],
        default='medium',
        validators=[DataRequired()],
        render_kw={'class': 'form-check-input'}
    )