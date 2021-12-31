# main.py

from flask import Blueprint, render_template, redirect, url_for, request, flash, send_from_directory, current_app
from flask_login import login_required, current_user
from .models import User, Platform, Device
from . import db
from datetime import datetime
import time
import re
from packaging import version # for semver support
import os

main = Blueprint('main', __name__)

def log_event(msg):
    st = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    print(st + ' ' + msg)

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


@main.context_processor
def utility_processor():
    def format_mac(mac):
        return ':'.join(mac[i:i+2] for i in range(0,12,2))
    return dict(format_mac=format_mac)

@main.route('/status')
@login_required
def status():
    platforms = Platform.query.all()
    return render_template('status.html', platforms=platforms)



@main.route('/update', methods=['GET'])
def update():
    __error = 400
    __dev = request.args.get('dev', default=None) # get requested device version
    if 'X_ESP8266_STA_MAC' in request.headers:
        __mac = request.headers['X_ESP8266_STA_MAC']
        __mac = str(re.sub(r'[^0-9A-fa-f]+', '', __mac.lower()))
        log_event("INFO: Update called by ESP8266 with MAC " + __mac)
    elif 'x_ESP32_STA_MAC' in request.headers:
        __mac = request.headers['x_ESP32_STA_MAC']
        __mac = str(re.sub(r'[^0-9A-fa-f]+', '', __mac.lower()))
        log_event("INFO: Update called by ESP32 with MAC " + __mac)
    else:
        __mac = ''
        log_event("WARN: Update called without known headers.")
    __ver = version.parse(request.args.get('ver', default=None)) # parse version, brings a bit extra safety
    if __dev and __mac and __ver:
        # If we know this device already
        device = Device.query.filter_by(mac=__mac).first()
        if device:
            device.last_seen = datetime.utcnow()
            device.version = str(__ver)
        else:
            device = Device(mac=__mac, version = str(__ver))
            # add the new device to the database
            db.session.add(device)
        db.session.commit()
 
        log_event("INFO: Device type: " + __dev + " Ver: " + str(__ver))
        __dev = __dev.lower()
        # platform = Platform.query.join(Device).filter(Device.mac).first()
        platform = Platform.query.filter_by(name = __dev).first()
        if platform: # device is known for a platform
            device_whitelisted = Platform.query.join(Device).filter(Device.mac== __mac).first()
            # device_whitelisted = True
            if device_whitelisted: 
                    if not platform.version: # when no file has been uploaded
                        log_event("ERROR: No update available.")
                        return 'No update available.', 400
                    if __ver < version.parse(platform.version):
                        if os.path.isfile(current_app.config['UPLOAD_FOLDER'] + '/' + platform.file):
                            platform.downloads += 1
                            db.session.commit()
                            return send_from_directory(directory=current_app.config['UPLOAD_FOLDER'], filename=platform.file,
                                                    as_attachment=True, mimetype='application/octet-stream',
                                                    attachment_filename=platform.file)
                    else:
                        log_event("INFO: No update needed.")
                        return 'No update needed.', 304
            else:
                log_event("ERROR: Device not whitelisted.")
                # Temporarily whitelist immediately! TODO: REMOVE THIS IN PROD!
                device.type = platform.id
                db.session.commit()
                return 'Error: Device not whitelisted.', 400
        else:
            log_event("ERROR: Unkown platform")
            return 'Error: Unkown platform', 500
    log_event("ERROR: Invalid parameters.")
    return 'Error: Invalid parameters.', 400