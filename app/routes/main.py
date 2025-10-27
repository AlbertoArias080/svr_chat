from flask import Blueprint, render_template
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    return render_template('home.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return render_template('admin/dashboard.html')
    else:
        return render_template('user/dashboard.html')

@main_bp.route('/chat')
@login_required
def user_chat():
    return render_template('user/chat.html')

# Ruta para crear un usuario admin por defecto (solo para desarrollo)
@main_bp.route('/create-admin')
def create_admin():
    from app.models import DynamoDB, User
    from werkzeug.security import generate_password_hash
    import uuid
    
    db = DynamoDB()
    admin_user = User(
        user_id=str(uuid.uuid4()),
        email='admin@bmc.com',
        password=generate_password_hash('admin123'),
        role='admin'
    )
    
    if db.create_user(admin_user):
        return "Usuario admin creado: admin@bmc.com / admin123"
    else:
        return "El usuario admin ya existe"