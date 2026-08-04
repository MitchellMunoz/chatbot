from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, PasswordField, BooleanField, SubmitField, DateField, TimeField, DecimalField
from wtforms.validators import DataRequired

class QuoteForm(FlaskForm):
    #name in models, String..('NAME ON HTML PAGE')
    quote_number = StringField('Quote Number')
    solicitor = StringField('Solicitor', validators=[DataRequired()])
    quoted_date = DateField('Quoted Date')
    quoted_time = TimeField('Quoted Time')
    source = StringField('Source')
    current_status = StringField('Current Status')
    primary_account_holder = StringField ('Name of')
    result = StringField('Result')
    points_category = StringField('Points Category')
    available_points = DecimalField('Available Points', places=2)
    available_bonus_points = DecimalField('Available Bonus Points', places=2)
    guest_fee = IntegerField('Guest Fee')
    hotel = StringField('Hotel')



###opus can only add below here### coment out the code above if needed S
