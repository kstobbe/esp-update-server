# models.py

from flask_login import UserMixin
from . import db
from sqlalchemy.sql import func


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))

class Platform(db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    name = db.Column(db.String(100), unique=True)
    version = db.Column(db.String(100))
    uploaded = db.Column(db.DateTime)
    notes = db.Column(db.String(1000)) # add any notes about the platform
    devices = db.relationship('Device', backref='platform', lazy=True)
    
class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    type = db.Column(db.Integer, db.ForeignKey('platform.id'), nullable=False)
    version = db.Column(db.String(100)) # last known version of the device.
    IP = db.Column(db.String(100))
    first_seen = db.Column(db.DateTime,server_default=func.utcnow())
    last_seen = db.Column(db.DateTime,server_default=func.utcnow())
    notes = db.Column(db.String(1000)) # add any notes about the platform
