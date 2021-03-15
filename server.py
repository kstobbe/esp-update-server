import os
import re
import time
from datetime import datetime

import yaml
from flask import (Flask, flash, redirect, render_template, request,
                   send_from_directory, url_for)
from packaging import version
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

__author__ = 'Kristian Stobbe'
__copyright__ = 'Copyright 2019, K. Stobbe'
__credits__ = ['Kristian Stobbe']
__license__ = 'MIT'
__version__ = '2.1.0'
__maintainer__ = 'Kristian Stobbe'
__email__ = 'mail@kstobbe.dk'
__status__ = 'Production'

ALLOWED_EXTENSIONS = set(['bin'])
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './bin'
app.config['SECRET_KEY'] = 'Kri57i4n570bb33r3nF1ink3rFyr'
PLATFORMS_YAML = app.config['UPLOAD_FOLDER'] + '/platforms.yml'
MACS_YAML = app.config['UPLOAD_FOLDER'] + '/macs.yml'
USERS_YAML = app.config['UPLOAD_FOLDER'] + '/users.yml'


auth = HTTPBasicAuth()

users = {}

@auth.verify_password
def verify_password(username, password):
    if username in users and \
            check_password_hash(users.get(username), password):
        return username

def log_event(msg):
    st = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    print(st + ' ' + msg)


def allowed_ext(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def load_yaml():
    platforms = None
    try:
        with open(PLATFORMS_YAML, 'r') as stream:
            try:
                platforms = yaml.load(stream, Loader=yaml.FullLoader)
            except yaml.YAMLError as err:
                flash(err)
    except:
        flash('Error: File not found.')
    if platforms:
        for value in platforms.values():
            if value['whitelist']:
                for i in range(0, len(value['whitelist'])):
                    value['whitelist'][i] = str(value['whitelist'][i])
    return platforms

def load_users():
    users = None
    try:
        with open(USERS_YAML, 'r') as stream:
            try:
                users = yaml.load(stream, Loader=yaml.FullLoader)
            except yaml.YAMLError as err:
                flash(err)
    except:
        flash('Error: Users file not found.')
    if users:
        for user in users: # generate hash from the plaintext password
            users[user] = generate_password_hash(users[user])
    if not users:
        users = dict()
    print(users)
    return users


def save_yaml(platforms):
    try:
        with open(PLATFORMS_YAML, 'w') as outfile:
            yaml.dump(platforms, outfile, default_flow_style=False)
            return True
    except:
        flash('Error: Data not saved.')
    return False


def load_known_mac_yaml():
    macs = None
    try:
        with open(MACS_YAML, 'r') as stream:
            try:
                macs = yaml.load(stream, Loader=yaml.FullLoader)
            except yaml.YAMLError as err:
                flash(err)
    except:
        flash('Error: File not found.')
    if macs:
        for known_mac in macs.values():
            if known_mac['first_seen']:
                known_mac['first_seen'] = str(known_mac['first_seen'])
            if known_mac['last_seen']:
                known_mac['last_seen'] = str(known_mac['last_seen'])
    if not macs:
        macs = dict()
    return macs


def save_known_mac_yaml(macs):
    try:
        with open(MACS_YAML, 'w') as outfile:
            yaml.dump(macs, outfile, default_flow_style=False)
            return True
    except:
        flash('Error: Known MAC data not saved.')
    return False


@app.context_processor
def utility_processor():
    def format_mac(mac):
        return ':'.join(mac[i:i+2] for i in range(0,12,2))
    return dict(format_mac=format_mac)


@app.route('/update', methods=['GET', 'POST'])
def update():
    __error = 400
    platforms = load_yaml()
    known_macs = load_known_mac_yaml()
    __dev = request.args.get('dev', default=None)
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
    __ver = request.args.get('ver', default=None)
    if __dev and __mac and __ver:
        # If we know this device already
        if __mac in known_macs.keys():
            known_macs[__mac]['last_seen'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        else:
            known_macs[__mac] = {'first_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                           'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                           'IP': None,
                           'type': None}
        save_known_mac_yaml(known_macs)
        log_event("INFO: Dev: " + __dev + "Ver: " + __ver)
        __dev = __dev.lower()
        if platforms:
            if __dev in platforms.keys():
                if __mac in platforms[__dev]['whitelist']:
                    if not platforms[__dev]['version']:
                        log_event("ERROR: No update available.")
                        return 'No update available.', 400
                    if version.parse(__ver) < version.parse(platforms[__dev]['version']):
                        if os.path.isfile(app.config['UPLOAD_FOLDER'] + '/' + platforms[__dev]['file']):
                            platforms[__dev]['downloads'] += 1
                            save_yaml(platforms)
                            return send_from_directory(directory=app.config['UPLOAD_FOLDER'], filename=platforms[__dev]['file'],
                                                       as_attachment=True, mimetype='application/octet-stream',
                                                       attachment_filename=platforms[__dev]['file'])
                    else:
                        log_event("INFO: No update needed.")
                        return 'No update needed.', 304
                else:
                    log_event("ERROR: Device not whitelisted.")
                    return 'Error: Device not whitelisted.', 400
            else:
                log_event("ERROR: Unknown platform.")
                return 'Error: Unknown platform.', 400
        else:
            log_event("ERROR: Create platforms before updating.")
            return 'Error: Create platforms before updating.', 500
    log_event("ERROR: Invalid parameters.")
    return 'Error: Invalid parameters.', 400

@app.route('/upload', methods=['GET', 'POST'])
@auth.login_required
def upload():
    platforms = load_yaml()
    if platforms and request.method == 'POST':
        if 'file' not in request.files:
            flash('Error: No file selected.')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Error: No file selected.')
            return redirect(request.url)
        if file and allowed_ext(file.filename):
            data = file.read()
            for __dev in platforms.keys():
                m = re.search(b"update\?dev=" + __dev.encode('UTF-8') + b"&ver=(v\d+\.\d+\.\d+)\x00", data, re.IGNORECASE)
                if m:
                    __ver = m.groups()[0][1:].decode('utf-8')
                    if (platforms[__dev]['version'] is None) or (platforms[__dev]['version'] and version.parse(platforms[__dev]['version']) < version.parse(__ver)):
                        old_file = platforms[__dev]['file']
                        filename = __dev + '_' + __ver.replace('.', '_') + '.bin'
                        platforms[__dev]['version'] = __ver
                        platforms[__dev]['downloads'] = 0
                        platforms[__dev]['file'] = filename
                        platforms[__dev]['uploaded'] = datetime.now().strftime('%Y-%m-%d')
                        file.seek(0)
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        file.close()
                        if save_yaml(platforms):
                            # Only delete old file after YAML file is updated.
                            if old_file:
                                try:
                                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], old_file))
                                except:
                                    flash('Error: Removing old file failed.')
                            flash('Success: File uploaded for platform {} with version {}.'.format(__dev, __ver))
                        else:
                            flash('Error: Could not save file.')
                        return redirect(url_for('index'))
                    else:
                        flash('Error: Version must increase. File not uploaded.')
                        return redirect(request.url)
            m = re.search(b"update\?dev=" + __dev.encode('UTF-8')+ b"&ver=$", data, re.IGNORECASE)
            if m: # a platform was found, meaning no version was found
                flash('Error: No version found in file. File not uploaded.')
                return redirect(request.url)
            else:
                flash('Error: No known platform name found in file. File not uploaded.')
                return redirect(request.url)
        else:
            flash('Error: File type not allowed.')
            return redirect(request.url)
    if platforms:
        return render_template('upload.html')
    else:
        return render_template('status.html', platforms=platforms)


@app.route('/create', methods=['GET', 'POST'])
@auth.login_required
def create():
    if request.method == 'POST':
        if not request.form['name']:
            flash('Error: Invalid name.')
        else:
            platforms = load_yaml()
            if not platforms:
                platforms = dict()
            platforms[request.form['name'].lower()] = {'version': None,
                           'file': None,
                           'uploaded': None,
                           'downloads': 0,
                           'whitelist': None}
            if save_yaml(platforms):
                flash('Success: Platform created.')
            else:
                flash('Error: Could not save file.')
            return render_template('status.html', platforms=platforms)
        return redirect(request.url)
    return render_template('create.html')


@app.route('/delete', methods=['GET', 'POST'])
@auth.login_required
def delete():
    if request.method == 'POST':
        if not request.form['name']:
            flash('Error: Invalid name.')
        else:
            platforms = load_yaml()
            if platforms and request.form['name'] in platforms.keys():
                old_file = platforms[request.form['name']]['file']
                del platforms[request.form['name']]
                if save_yaml(platforms):
                    flash('Success: Platform deleted.')
                else:
                    flash('Error: Could not save file.')
                # Only delete old file after YAML file is updated.
                if old_file:
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], old_file))
                    except:
                        flash('Error: Removing old file failed.')
            return render_template('status.html', platforms=platforms)
        return redirect(request.url)
    platforms = load_yaml()
    if platforms:
        return render_template('delete.html', names=platforms.keys())
    else:
        return render_template('status.html', platforms=platforms)


@app.route('/whitelist', methods=['GET', 'POST'])
@auth.login_required
def whitelist():
    platforms = load_yaml()
    known_macs = load_known_mac_yaml()
    if platforms and request.method == 'POST':
        if 'Add' in request.form['action']:
            # Ensure valid data.
            if request.form['device'] and request.form['device'] != '--' and request.form['macaddr']:
                # Remove all unwanted characters.
                __mac = str(re.sub(r'[^0-9A-fa-f]+', '', request.form['macaddr']).lower())
                # Check length after clean-up makes up a full address.
                if len(__mac) == 12:
                    # Check that address is not already on a whitelist.
                    for value in platforms.values():
                        if value['whitelist'] and __mac in value['whitelist']:
                            flash('Error: Address already on a whitelist.')
                            return render_template('whitelist.html', platforms=platforms)
                    # All looks good - add to whitelist.
                    if not platforms[request.form['device']]['whitelist']:
                        platforms[request.form['device']]['whitelist'] = []
                    platforms[request.form['device']]['whitelist'].append(__mac)
                    if save_yaml(platforms):
                        flash('Success: Address added.')
                    else:
                        flash('Error: Could not save file.')
                else:
                    flash('Error: Address malformed.')
            else:
                flash('Error: No data entered.')
        elif 'Remove' in request.form['action']:
            platforms[request.form['device']]['whitelist'].remove(str(request.form['macaddr']))
            if save_yaml(platforms):
                flash('Success: Address removed.')
            else:
                flash('Error: Could not save file.')
        else:
            flash('Error: Unknown action.')

    if platforms:
        return render_template('whitelist.html', platforms=platforms, known_macs = known_macs)
    else:
        return render_template('status.html', platforms=platforms)

@app.route('/')
@auth.login_required
def index():
    platforms = load_yaml()
    return render_template('status.html', platforms=platforms)


if __name__ == '__main__':
    users = load_users()
    app.run(host='0.0.0.0', port=int('5000'), debug=False)
