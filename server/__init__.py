# init.py

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager 
from flask_moment import Moment
from werkzeug.security import generate_password_hash

# init SQLAlchemy so we can use it later in our models
db = SQLAlchemy()
moment = Moment()
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration



def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = 'SECRET_KEY_HERE'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bin/db.sqlite'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
    app.config['UPLOAD_FOLDER'] = 'bin' # where to store the uploaded firmware-files
    app.config['ALLOWED_EXTENSIONS'] = set(['bin']) # set the file-extensions that users are allowed to upload here
    app.config['DELETE_OLD_FILES'] = True # Do we delete old binaries after a new one has been uploaded
    db.init_app(app)
    moment.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from .models import User, Platform, Device
    with app.app_context():
        db.create_all()  # a bit dirty, but push the app context, so sqlalchemy knows about the context, and then create all tables

    # check if we need to add an Admin-user
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
    if ADMIN_EMAIL and ADMIN_PASSWORD:
        with app.app_context():
            user = User.query.filter_by(email=ADMIN_EMAIL).first() # if this returns a user, then the email already exists in database
            if user: # if a user is found, we want to make it an admin
                user.admin = True  
            else:
                # create new user with the supplied data. Hash the password so plaintext version isn't saved.
                new_user = User(email=ADMIN_EMAIL, name="Admin", password=generate_password_hash(ADMIN_PASSWORD, method='sha256'), admin=True)
                # add the new user to the database
                db.session.add(new_user)
            # store all changes
            db.session.commit()

    @login_manager.user_loader
    def load_user(user_id):
        # since the user_id is just the primary key of our user table, use it in the query for the user
        return User.query.get(int(user_id))

    # blueprint for auth routes in our app
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    # blueprint for non-auth parts of app
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    sentry_sdk.init(
    dsn="https://ccfebfa76dc645acbc16566836763e5b@o231748.ingest.sentry.io/6118097",
    integrations=[FlaskIntegration()],

    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=1.0
)


    return app