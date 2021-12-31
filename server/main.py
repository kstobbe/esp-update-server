# main.py

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from .models import User, Platform, Device
from . import db

main = Blueprint('main', __name__)

@main.route('/')
def index():
    db.create_all() # a bit dirty, but create all tables on load of the main. Doesn't re-create any already existing tables
    return render_template('index.html')

@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html', name=current_user.name)



@main.route('/create')
def create():
    return render_template('create.html')


@main.route('/create', methods=['POST'])
@login_required
def create_post():
    
    platform_name = request.form.get('name')
    if not platform_name:
        flash("No platform name entered")
        return redirect(url_for('main.create'))
    
    
    platform = Platform.query.filter_by(name=platform_name).first() # if this returns a user, then the email already exists in database
    if platform:
        flash('Platform already exists')
        return redirect(url_for('main.create'))

    notes = request.form.get('notes')
     # Create a new platform using this information
    new_platform = Platform(name = platform_name, notes = notes)
    # add the new user to the database
    db.session.add(new_platform)
    db.session.commit()
    return redirect(url_for('main.index'))