from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from babel.dates import format_datetime
from pytz import timezone

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def to_ph_time(value, fmt='short'):
    """Custom Jinja filter to format datetime to Asia/Manila timezone"""
    if not value:
        return ""
    ph_tz = timezone('Asia/Manila')
    return format_datetime(value, fmt, tzinfo=ph_tz, locale='en_PH')

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'ITAdmin09457719417@cruz34621'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../instance/app.db'

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    # Register Jinja filters
    app.jinja_env.filters['format_datetime'] = format_datetime  # Default
    app.jinja_env.filters['to_ph_time'] = to_ph_time            # Custom PH time

    # Register blueprint
    from .routes import main
    app.register_blueprint(main)

    return app
