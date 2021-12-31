# models.py

from flask_login import UserMixin
from . import db
from sqlalchemy.sql import func


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    admin = db.Column(db.Boolean())

class Platform(db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    name = db.Column(db.String(100), unique=True)
    version = db.Column(db.String(100))
    uploaded = db.Column(db.DateTime)
    notes = db.Column(db.String(1000)) # add any notes about the platform
    devices = db.relationship('Device', backref='platform', lazy=True)
    file = db.Column(db.String(100))
    downloads = db.Column(db.Integer, default = 0)
    
class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    type = db.Column(db.Integer, db.ForeignKey('platform.id'))
    version = db.Column(db.String(100)) # last known version of the device.
    IP = db.Column(db.String(100)) 
    first_seen = db.Column(db.DateTime,server_default=func.now())
    last_seen = db.Column(db.DateTime,server_default=func.now())
    notes = db.Column(db.String(1000)) # add any notes about the platform
    mac = db.Column(db.String(17),nullable = False) # aa:bb:cc:dd:de:ff
    requested_platform = db.Column(db.String(100)) # the name of the platform that the device thinks it is

