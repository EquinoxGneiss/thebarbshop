from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'ITAdmin09457719417@cruz34621'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../instance/app.db'

    db.init_app(app)                # ✅ only once
    migrate.init_app(app, db)       # ✅ good
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    from .routes import main
    app.register_blueprint(main)

    return app
