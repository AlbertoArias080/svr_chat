from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, SelectField, SubmitField, TextAreaField


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=6, message='La contraseña debe tener al menos 6 caracteres')
    ])
    confirm = PasswordField('Confirmar Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Las contraseñas deben coincidir')
    ])
    submit = SubmitField('Crear Cuenta')

class DocumentUploadForm(FlaskForm):
    document = FileField('Documento', validators=[
        FileRequired(message='Por favor selecciona un archivo'),
        FileAllowed([
            'pdf', 'doc', 'docx', 'txt', 
            'jpg', 'jpeg', 'png', 'gif',
            'xls', 'xlsx', 'ppt', 'pptx'
        ], 'Solo se permiten documentos e imágenes')
    ])
    description = StringField('Descripción', validators=[
        DataRequired(message='La descripción es requerida'),
        Length(max=200, message='La descripción no puede tener más de 200 caracteres')
    ])
    category = SelectField('Categoría', choices=[
        ('', 'Seleccionar categoría'),
        ('reportes', '📊 Reportes'),
        ('manuales', '📖 Manuales'),
        ('contratos', '📝 Contratos'),
        ('facturas', '🧾 Facturas'),
        ('imagenes', '🖼️ Imágenes'),
        ('otros', '📁 Otros')
    ], validators=[DataRequired(message='La categoría es requerida')])
    submit = SubmitField('📤 Subir Documento')