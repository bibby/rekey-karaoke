#!/usr/bin/env python
import os
import re
from datetime import datetime

import flask_login
import validators
from flask import Flask, request, render_template, url_for, redirect, abort
from flask_cors import CORS
from redis import StrictRedis

from db import db, User, TrackFlags, Track, TrackStatus, files_data_for, COMMON_KEYS
from server.log import logger
from server.util import serial

env = os.environ.get
app = Flask(__name__)
app.secret_key = '2f06ddab-032f-48ce-b280-8d56f8a87524'
login_manager = flask_login.LoginManager()
login_manager.init_app(app)
CORS(app)

app.config['UPLOAD_EXTENSIONS'] = ['.mp3', '.wav']
app.config['UPLOAD_PATH'] = env('UPLOAD_DIR', '/tmp/uploads')
app.config['OUTPUT_DIR'] = env('OUTPUT_DIR', '/tmp/spleets')
app.config['REDIS_HOST'] = env('REDIS_HOST', 'localhost')

red = StrictRedis(host=app.config['REDIS_HOST'])


def get_or_create_user(username, by_id=False):
    if not username:
        return

    try:
        if by_id:
            user = User.get(username)
        else:
            user = User.get(User.username == username)
    except User.DoesNotExist:
        user = User(username=username)
        user.save()

    return user


@login_manager.user_loader
def user_loader(id):
    return get_or_create_user(id, by_id=True)


@login_manager.request_loader
def request_loader(request):
    username = request.form.get('username')
    if not username:
        return None

    return get_or_create_user(username)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.j2', title='Login')

    user = request_loader(request)
    if not user:
        return render_template('login.j2', title='Login')

    flask_login.login_user(user)
    return redirect(url_for('index'))


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('login'))


@app.route('/')
@flask_login.login_required
def index():
    return render_template('index.j2', title='Index', common_keys=', '.join(COMMON_KEYS))


@app.route('/logout')
def logout():
    flask_login.logout_user()
    return render_template('logout.j2', title='Logout')


@app.before_request
def setup():
    db.connect()


def from_form(key):
    try:
        return request.form[key]
    except Exception as e:
        return None


def is_checked(key):
    return from_form(key) == 'on'


@flask_login.login_required
@app.route('/add', methods=['POST'])
def add_job():
    flags = 0
    raised = [
        (is_checked('skip_split'), TrackFlags.SKIP_SPLIT),
        (is_checked('skip_rekey'), TrackFlags.SKIP_REKEY),
        (is_checked('is_private'), TrackFlags.PRIVATE),
        (is_checked('rekey_common'), TrackFlags.REKEY_COMMON),
        (is_checked('prioritize_split'), TrackFlags.NOVOX_FIRST),
    ]

    for add, flag in raised:
        if add:
            flags += flag.value

    url = from_form('url').strip(' ')

    if not url:
        return redirect(url_for('index', error='you forgot a url'))

    url = valid_url(url)
    if not url:
        return redirect(url_for('index', error="That doesn't look like a url to me."))

    try:
        return create_job(url, flags)
    except Exception as e:
        return redirect(url_for('index', error=str(e)))


def valid_url(url):
    try:
        if not validators.url(url):
            return None
        return re.sub('[=&]pp=[a-zA-Z0-9%]+', '', url)
    except:
        logger.warn(f"Invalid URL: {url}")
        return None


@flask_login.login_required
@app.route('/tracks', methods=['GET'])
def job_list():
    try:
        tracks = Track.select().order_by(Track.updated.desc())
        tracks = filter_private(tracks)
        tracks = serial(list(tracks), raw=True)
    except Track.DoesNotExist:
        tracks = []

    return render_template('songs.j2', tracks=tracks, now=datetime.now())


def filter_private(tracks):
    keep = []
    for t in tracks:
        me = t.user == flask_login.current_user
        public = not t.has_flag(TrackFlags.PRIVATE)
        if me or public:
            keep.append(t)

    return keep


@app.route('/track/<uuid:uuid>', methods=['GET'])
def view_track(uuid):
    return render_track(uuid, 'track.j2')


@app.route('/poll/<uuid:uuid>', methods=['GET'])
def poll_track(uuid):
    return render_track(uuid, 'track_inner.j2')


def render_track(uuid, tpl):
    try:
        track = Track.get(Track.uuid == uuid)
    except Track.DoesNotExist as e:
        abort(404)

    now = datetime.now()
    context = dict(
        track=track.serial(),
        files=files_data_for(track),
        now=serial(now),
        updated_delta=serial(track.updated - track.created),
        now_delta=serial(now - track.created),
        is_done=track.is_status([TrackStatus.DONE, TrackStatus.ERROR]),
    )

    return render_template(tpl, **context)


def create_job(url, flags):
    track = Track(
        url=url,
        flags=flags,
        user=flask_login.current_user,
        status=TrackStatus.QUEUED
    )

    track.save()
    track.next_status(red)

    return redirect(url_for('view_track', uuid=track.uuid))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1337)
