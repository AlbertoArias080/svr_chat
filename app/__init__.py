from flask import Flask
from flask_login import LoginManager
from config import Config

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'info'

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    login_manager.init_app(app)

    # Importar e inicializar la base de datos
    from app.models import DynamoDB
    db = DynamoDB()
    
    # Inicializar tablas necesarias
    try:
        print("📋 Inicializando tablas de DynamoDB...")
        db.create_documents_table()
        print("✅ Tabla 'documents' inicializada")
    except Exception as e:
        print(f"⚠️  Error inicializando tabla documents: {e}")
    
    try:
        db.create_chat_table()
        print("✅ Tabla 'chat_messages' inicializada")
    except Exception as e:
        print(f"⚠️  Error inicializando tabla chat_messages: {e}")

    # Importar blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.chat import chat_bp
    
    # Registrar blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(chat_bp)

    @login_manager.user_loader
    def load_user(user_id):
        return db.get_user_by_id(user_id)

    return app