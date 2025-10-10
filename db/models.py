from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime
from flask import current_app
from sqlalchemy import text
from db import db

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    credits_remaining = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SessionTemp(db.Model):
    __tablename__ = "sessions"
    session_id = db.Column(db.String(64), primary_key=True)
    ip_hash = db.Column(db.String(64), index=True)
    ua_hash = db.Column(db.String(64), index=True)
    credits_temp_remaining = db.Column(db.Integer, default=0)
    migrated_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Analysis(db.Model):
    __tablename__ = "analyses"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), db.ForeignKey("sessions.session_id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    type = db.Column(db.String(16))  # "photo" | "text"
    meta_json = db.Column(db.Text)
    score_risk = db.Column(db.Integer, default=0)
    tags_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Purchase(db.Model):
    __tablename__ = "purchases"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    package = db.Column(db.Integer)  # créditos adicionados
    amount = db.Column(db.Integer)   # centavos (se necessário)
    status = db.Column(db.String(32))
    provider_ref = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@contextmanager
def with_transaction():
    try:
        yield
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
