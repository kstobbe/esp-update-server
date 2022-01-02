# main.py

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    send_from_directory,
    current_app,
)
from flask_login import login_required, current_user
from sqlalchemy.sql.expression import desc
from .models import User, Platform, Device
from . import db
from datetime import datetime
import time
import re
from packaging import version  # for semver support
import os

main = Blueprint("main", __name__)

# Returns true if the extension of `filename` is allowed
def allowed_ext(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]

def log_event(msg):
    st = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
    print(st + " " + msg)


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/profile")
@login_required
def profile():
    return render_template("profile.html", name=current_user.name)


@main.route("/create")
@login_required
def create():
    return render_template("create.html")


@main.route("/create", methods=["POST"])
@login_required
def create_post():

    platform_name = request.form.get("name")
    if not platform_name:
        flash("No platform name entered")
        return redirect(url_for("main.create"))

    platform = Platform.query.filter_by(
        name=platform_name
    ).first()  # if this returns a user, then the email already exists in database
    if platform:
        flash("Platform already exists")
        return redirect(url_for("main.create"))

    notes = request.form.get("notes")
    # Create a new platform using this information
    new_platform = Platform(name=platform_name, notes=notes)
    # add the new user to the database
    db.session.add(new_platform)
    db.session.commit()
    return redirect(url_for("main.whitelist"))


@main.context_processor
def utility_processor():
    def format_mac(mac):
        return ":".join(mac[i : i + 2] for i in range(0, 12, 2))

    return dict(format_mac=format_mac)


@main.route("/whitelist")
@login_required
def whitelist():
    platforms = Platform.query.all()
    unbound_devices = Device.query.filter_by(type=None).order_by(desc(Device.last_seen))
    return render_template("whitelist.html", platforms=platforms,unbound_devices=unbound_devices)

@main.route('/whitelist', methods=['POST'])
@login_required
def whitelist_post():
    platforms = Platform.query.all()
    unbound_devices = Device.query.filter_by(type=None).order_by(desc(Device.last_seen))
    # Delete platform binding
    if request.form.get('_method') and 'DELETE' in request.form.get('_method'):
        if request.form['_device']:
            device_id = request.form.get('_device',type=int)
            device = Device.query.filter_by(id=device_id).first()
            device.type = None # Set the type to None, instead of deleting the device completely
            db.session.commit()
            flash("Deleted device from platform")

    # Edit notes
    if request.form.get('_method') and 'NOTES' in request.form.get('_method'):
        if request.form['_device']:
            device_id = request.form.get('_device',type=int)
            device = Device.query.filter_by(id=device_id).first()
            device.notes = request.form.get('_notes') # update the note
            db.session.commit()
            flash("Updated note")

    elif request.form.get('action') and 'ADD' in request.form.get('action'):
        # Ensure valid data.
        if request.form['device'] and request.form['device'] != '--' and request.form['macaddr']:
            # Remove all unwanted characters.
            __mac = str(re.sub(r'[^0-9A-fa-f]+', '', request.form['macaddr']).lower())
            # Check length after clean-up makes up a full address.
            if len(__mac) == 12:
                # Check that address is not already on a whitelist.
                known_device = Device.query.filter_by(mac=__mac).first()
                if not known_device:
                    flash('Error: Unknown device. Let the device connect to the OTA server before adding')
                    return render_template("whitelist.html", platforms=platforms, unbound_devices=unbound_devices)
                if known_device.type: 
                        flash('Error: Address already on a whitelist.')
                        return render_template("whitelist.html", platforms=platforms, unbound_devices=unbound_devices)
                # All looks good - add to whitelist.
                known_platform = Platform.query.filter_by(name=request.form['device']).first()
                if known_device and known_platform:
                    known_device.type = known_platform.id
                    known_device.notes = request.form.get('notes')
                    db.session.commit()
                    flash('Success: {} added to platform {}'.format(known_device.mac, known_platform.name))
                else:
                    flash('Error: Platform unkown')
            else:
                flash('Error: MAC address malformed.')
        else:
            flash('Error: No data entered.')
    else:
        flash('Error: Unknown action.')
    return render_template("whitelist.html", platforms=platforms, unbound_devices=unbound_devices)

@main.route("/update", methods=["GET"])
def update():
    __error = 400
    __dev = request.args.get("dev", default=None)  # get requested device version
    if "X_ESP8266_STA_MAC" in request.headers:
        __mac = request.headers["X_ESP8266_STA_MAC"]
        __mac = str(re.sub(r"[^0-9A-fa-f]+", "", __mac.lower()))
        log_event("INFO: Update called by ESP8266 with MAC " + __mac)
    elif "x_ESP32_STA_MAC" in request.headers:
        __mac = request.headers["x_ESP32_STA_MAC"]
        __mac = str(re.sub(r"[^0-9A-fa-f]+", "", __mac.lower()))
        log_event("INFO: Update called by ESP32 with MAC " + __mac)
    else:
        __mac = ""
        log_event("WARN: Update called without known headers.")
    __ver = version.parse(
        request.args.get("ver", default=None)
    )  # parse version, brings a bit extra safety
    if __dev and __mac and __ver and len(__mac) == 12:
        # If we know this device already
        device = Device.query.filter_by(mac=__mac).first()
        if device:
            device.last_seen = datetime.utcnow()
            device.version = str(__ver)
            device.requested_platform = __dev
            device.IP = request.remote_addr
        else:
            device = Device(mac=__mac, version=str(__ver), requested_platform=__dev, IP=request.remote_addr)
            # add the new device to the database
            db.session.add(device)
        db.session.commit()

        log_event("INFO: Device type: " + __dev + " Ver: " + str(__ver))
        __dev = __dev.lower()
        platform = Platform.query.filter_by(name=__dev).first()
        if platform:  # device is known for a platform
            device_whitelisted = (
                Platform.query.join(Device).filter(Device.mac == __mac).first()
            )
            # device_whitelisted = True
            if device_whitelisted:
                if not platform.version:  # when no file has been uploaded
                    log_event("ERROR: No update available.")
                    return "No update available.", 400
                if __ver < version.parse(platform.version):
                    if os.path.isfile(
                        current_app.config["UPLOAD_FOLDER"] + "/" + platform.file
                    ):
                        platform.downloads += 1
                        db.session.commit()
                        return send_from_directory(
                            directory=current_app.config["UPLOAD_FOLDER"],
                            filename=platform.file,
                            as_attachment=True,
                            mimetype="application/octet-stream",
                            attachment_filename=platform.file,
                        )
                else:
                    log_event("INFO: No update needed.")
                    return "No update needed.", 304
            else:
                log_event("ERROR: Device not whitelisted.")
                return "Error: Device not whitelisted.", 400
        else:
            log_event("ERROR: Unkown platform")
            return "Error: Unkown platform", 500
    log_event("ERROR: Invalid parameters.")
    return "Error: Invalid parameters.", 400


@main.route("/upload")
@login_required
def upload():
    return render_template("upload.html")


@main.route("/upload", methods=["POST"])
@login_required
def upload_post():
    if 'file' not in request.files:
        flash('Error: No file selected.')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '' or not allowed_ext(file.filename):
        flash('Error: File upload error or wrong extension. Make sure you upload a file with the extension(s): {}'.format(str(current_app.config["ALLOWED_EXTENSIONS"])))
        return redirect(request.url)
    if file and allowed_ext(file.filename):
        data = file.read()
        platforms = Platform.query.all()
        # for every platform that we have, we search if this platform is named in the binary and try to extract a version-number
        for platform in platforms:
            m = re.search(b"update\?dev=" + platform.name.encode('UTF-8') + b"&ver=(v\d+\.\d+\.\d+)\x00", data, re.IGNORECASE)
            if m: # platform found!
                __ver = m.groups()[0][1:].decode('utf-8')
                # check if the uploaded file is an update to the version that we have in the database
                if (platform.version is None) or (platform.version and version.parse(platform.version ) < version.parse(__ver)):
                    old_file = platform.file
                    filename = platform.name + '_' + __ver.replace('.', '_') + '.bin'
                    platform.version = __ver
                    platform.downloads = 0 # reset download-counter
                    platform.file = filename.lower()
                    platform.uploaded = datetime.utcnow()
                    file.seek(0)
                    file.save(os.path.join(os.path.dirname(__file__), current_app.config['UPLOAD_FOLDER'], filename))
                    file.close()
                    db.session.commit()
                    # Only delete old file after db is updated; so the old file will not be deleted 
                    if old_file and current_app.config['DELETE_OLD_FILES']:
                        try:
                            os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], old_file))
                        except:
                            flash('Error: Removing old file failed.')
                    flash('Success: File uploaded for platform {} with version {}.'.format(platform.name, __ver))
                    return redirect(url_for('main.whitelist'))
                else:
                    flash('Error: Version must increase. File not uploaded.')
                    return redirect(request.url)
        m = re.search(b"update\?dev=" + platform.name.encode('UTF-8')+ b"&ver=$", data, re.IGNORECASE)
        if m: # only a platform was found, meaning no version was found
            flash('Error: No version found in file. File not uploaded.')
            return redirect(request.url)
        else:
            flash('Error: No known platform name found in file. File not uploaded.')
            return redirect(request.url)
    else:
        flash('Error: File type not allowed.')
        return redirect(request.url)

