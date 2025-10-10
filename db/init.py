from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db(app):
    db.init_app(app)
    with app.app_context():
        from db.models import User, SessionTemp, Analysis, Purchase  # noqa
        db.create_all()
