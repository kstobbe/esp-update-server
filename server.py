from datetime import datetime
from flask import Flask, request, render_template, flash, redirect, url_for, send_from_directory
from packaging import version
import re
import time
import os
import yaml

__author__ = 'Kristian Stobbe'
__copyright__ = 'Copyright 2019, K. Stobbe'
__credits__ = ['Kristian Stobbe']
__license__ = 'MIT'
__version__ = '1.1.0'
__maintainer__ = 'Kristian Stobbe'
__email__ = 'mail@kstobbe.dk'
__status__ = 'Production'

ALLOWED_EXTENSIONS = set(['bin'])
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './bin'
app.config['SECRET_KEY'] = 'Kri57i4n570bb33r3nF1ink3rFyr'
PLATFORMS_YAML = app.config['UPLOAD_FOLDER'] + '/platforms.yml'


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


def save_yaml(platforms):
    try:
        with open(PLATFORMS_YAML, 'w') as outfile:
            yaml.dump(platforms, outfile, default_flow_style=False)
            return True
    except:
        flash('Error: Data not saved.')
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
        log_event("INFO: Dev: " + __dev + "Ver: " + __ver)
        __dev = __dev.lower()
        if platforms:
            if __dev in platforms.keys():
                if __mac in platforms[__dev]['whitelist']:
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
                if re.search(__dev.encode('UTF-8'), data, re.IGNORECASE):
                    m = re.search(b'v\d+\.\d+\.\d+', data)
                    if m:
                        __ver = m.group()[1:].decode('utf-8')
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
                                flash('Success: File uploaded.')
                            else:
                                flash('Error: Could not save file.')
                            return redirect(url_for('index'))
                        else:
                            flash('Error: Version must increase. File not uploaded.')
                            return redirect(request.url)
                    else:
                        flash('Error: No version found in file. File not uploaded.')
                        return redirect(request.url)
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
def whitelist():
    platforms = load_yaml()
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
        return render_template('whitelist.html', platforms=platforms)
    else:
        return render_template('status.html', platforms=platforms)


@app.route('/')
def index():
    platforms = load_yaml()
    return render_template('status.html', platforms=platforms)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int('5000'), debug=False)
