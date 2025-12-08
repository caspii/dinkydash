"""
Countdown management forms.
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileSize
from wtforms import StringField, RadioField, SelectField, IntegerField, ValidationError
from wtforms.validators import DataRequired, Optional, Length, NumberRange
import calendar


class CountdownForm(FlaskForm):
    """Form for creating/editing countdown events."""
    
    name = StringField(
        'Event Name',
        validators=[
            DataRequired(message='Event name is required'),
            Length(min=1, max=100, message='Event name must be between 1 and 100 characters')
        ],
        render_kw={'placeholder': 'e.g., Christmas', 'class': 'form-control'}
    )
    
    dashboard_id = SelectField(
        'Dashboard',
        validators=[DataRequired(message='Please select a dashboard')],
        coerce=int,
        render_kw={'class': 'form-control'}
    )
    
    date_month = SelectField(
        'Month',
        validators=[DataRequired(message='Please select a month')],
        coerce=int,
        choices=[(i, calendar.month_name[i]) for i in range(1, 13)],
        render_kw={'class': 'form-control'}
    )
    
    date_day = IntegerField(
        'Day',
        validators=[
            DataRequired(message='Day is required'),
            NumberRange(min=1, max=31, message='Day must be between 1 and 31')
        ],
        render_kw={'placeholder': '25', 'class': 'form-control'}
    )
    
    icon_type = RadioField(
        'Icon Type',
        choices=[('emoji', 'Emoji'), ('image', 'Upload Image')],
        default='emoji',
        validators=[DataRequired()],
        render_kw={'class': 'form-check-input'}
    )
    
    emoji = StringField(
        'Emoji',
        validators=[Optional(), Length(max=10)],
        render_kw={'placeholder': '🎄', 'class': 'form-control'}
    )
    
    image = FileField(
        'Image',
        validators=[
            Optional(),
            FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Only JPG, PNG & GIF files are allowed'),
            FileSize(max_size=5*1024*1024, message='Image file size must be less than 5MB')
        ]
    )
    
    def validate(self, extra_validators=None):
        """Custom validation to ensure emoji/image requirements and valid date."""
        # First run standard validations
        if not super().validate(extra_validators):
            return False
        
        # Custom validation: if icon_type is emoji, emoji field is required
        if self.icon_type.data == 'emoji' and not self.emoji.data:
            self.emoji.errors.append('Emoji is required when emoji icon type is selected')
            return False
        
        # Custom validation: Check if the date is valid
        if self.date_month.data and self.date_day.data:
            try:
                # Check if day is valid for the given month
                # Use a non-leap year for general validation
                max_day = calendar.monthrange(2023, self.date_month.data)[1]
                if self.date_day.data > max_day:
                    self.date_day.errors.append(
                        f'{calendar.month_name[self.date_month.data]} only has {max_day} days'
                    )
                    return False
            except ValueError:
                self.date_day.errors.append('Invalid date')
                return False
        
        return True