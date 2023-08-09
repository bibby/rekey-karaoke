import os
import re
from abc import ABC
from datetime import datetime
from enum import Enum
from uuid import uuid4

from flask_login import UserMixin
from peewee import *

from server.consts import ORIGINAL_KEY, S3_BUCKET, DATABASE_FILE
from server.log import logger
from server.util import key_for, signed, offset_key, primitives

db_file = DATABASE_FILE
db = SqliteDatabase(db_file)
mktables = not os.path.isfile(db_file)

COMMON_KEYS = ['F', 'C', 'G', 'D', 'A']


class EnumField(IntegerField, ABC):
    def __init__(self, enum, *args, **kwargs):
        super(IntegerField, self).__init__(*args, **kwargs)
        self.enum = enum

    def db_value(self, value):
        return value.value

    def python_value(self, value):
        return self.enum(value)


class BaseModel(Model):
    created = DateTimeField(default=datetime.now)
    updated = DateTimeField(default=datetime.now)

    def save(self, *args, **kwargs):
        self.updated = datetime.now()
        super(BaseModel, self).save(*args, **kwargs)

    class Meta:
        database = db

    def serial(self):
        raise NotImplementedError('')


class TrackStatus(Enum):
    QUEUED = 0
    NEEDS_METADATA = 1
    GETTING_METADATA = 2
    NEEDS_DOWNLOAD = 3
    DOWNLOADING = 4
    NEEDS_KEYDETECT = 5
    GETTING_KEY = 6
    NEEDS_SPLIT = 7
    SPLITTING = 8
    NEEDS_REKEY = 9
    REKEYING = 10

    NEEDS_CLEANUP = 20
    CLEANING_UP = 21

    DONE = 30

    ERROR = 50
    REJECTED = 51


class FileStatus(Enum):
    QUEUED = 0
    WORKING = 1
    NEEDS_ENCODING = 2
    ENCODING = 3
    NEEDS_UPLOAD = 4
    UPLOADING = 5
    DONE = 20
    ERROR = 50


class FileType(Enum):
    NORMAL_AUDIO = 0
    INSTRUMENTAL_AUDIO = 1
    NORMAL_VIDEO = 2
    INSTRUMENTAL_VIDEO = 3


def ext_for(file_type):
    exts = {
        FileType.NORMAL_AUDIO: 'mp3',
        FileType.INSTRUMENTAL_AUDIO: 'mp3',
        FileType.NORMAL_VIDEO: 'mp4',
        FileType.INSTRUMENTAL_VIDEO: 'mp4',
    }

    return exts.get(file_type, None)


class Queue(Enum):
    METADATA = 'meta'
    DOWNLOAD = 'download'
    KEY_DETECT = 'key_detect'
    SPLIT = 'spleet'
    REKEY = 'rekey'
    ENCODE = 'encode'
    UPLOAD = 'upload'
    CLEANUP = 'cleanup'


def status_name(enum):
    return enum.name


class User(BaseModel, UserMixin):
    username = CharField()

    def serial(self):
        return dict(username=self.username)

    def __str__(self):
        return "{} ({})".format(self.username, self.id)


class TrackFlags(Enum):
    SKIP_SPLIT = 1 << 0
    SKIP_REKEY = 1 << 1
    PRIVATE = 1 << 2
    RESTITCH_VIDEO = 1 << 3
    REKEY_COMMON = 1 << 4
    NOVOX_FIRST = 1 << 5


class Track(BaseModel):
    url = CharField()
    uuid = UUIDField(default=uuid4)
    title = CharField(null=True)
    status = EnumField(TrackStatus)
    key = CharField(null=True)
    quality = CharField(null=True)
    thumbnail = CharField(null=True)
    duration = CharField(null=True)
    flags = IntegerField(default=0)
    user = ForeignKeyField(User)
    error_message = CharField(null=True)

    @property
    def status_enum(self):
        return TrackStatus

    @property
    def error_status(self):
        return TrackStatus.ERROR

    def set_status(self, status):
        self.status = status
        self.save()

    def expect_status(self, status):
        if not self.is_status(status):
            raise ValueError('Expected status {} but got {}', status, self.status)

    def is_status(self, statuses):
        if not isinstance(statuses, list):
            statuses = [statuses]
        return self.status in statuses

    def next_status(self, red):
        status = self._next_status()
        if status and status != self.status:
            self.set_status(status)

            if status == self.status_enum.NEEDS_METADATA:
                return red.rpush(Queue.METADATA.value, key_for(self))

            if status == self.status_enum.NEEDS_DOWNLOAD:
                return red.rpush(Queue.DOWNLOAD.value, key_for(self))

            if status == self.status_enum.NEEDS_KEYDETECT:
                return red.rpush(Queue.KEY_DETECT.value, key_for(self))

            if status == self.status_enum.NEEDS_SPLIT:
                return red.rpush(Queue.SPLIT.value, key_for(self))

            if status == self.status_enum.NEEDS_REKEY:
                key_offsets = list(range(-6, 7))
                # key_offsets = [-1, 1]

                key_offsets = sorted(key_offsets, key=lambda k: (abs(k) * 10) + int(k < 0))
                key_offsets = [i for i in key_offsets if i != ORIGINAL_KEY]

                if self.has_flag(TrackFlags.REKEY_COMMON):
                    key_offsets = [k for k in key_offsets if offset_key(self.key, k) in COMMON_KEYS]

                do_splits = not self.has_flag(TrackFlags.SKIP_SPLIT)

                keys = TrackFile.prepare(self, key_offsets, do_splits)
                for key in keys:
                    red.rpush(Queue.REKEY.value, key)

    def _next_status(self):
        enums = self.status_enum
        if self.status == enums.ERROR:
            return enums.ERROR

        if self.status == enums.QUEUED:
            return enums.NEEDS_METADATA

        if self.status == enums.NEEDS_METADATA:
            return enums.GETTING_METADATA

        if self.status == enums.GETTING_METADATA:
            return enums.NEEDS_DOWNLOAD

        if self.status == enums.NEEDS_DOWNLOAD:
            return enums.DOWNLOADING

        if self.status == enums.DOWNLOADING:
            return enums.NEEDS_KEYDETECT

        if self.status == enums.NEEDS_KEYDETECT:
            return enums.GETTING_KEY

        if self.status == enums.GETTING_KEY:
            if not self.has_flag(TrackFlags.SKIP_SPLIT):
                return enums.NEEDS_SPLIT
            if not self.has_flag(TrackFlags.SKIP_REKEY):
                return enums.NEEDS_REKEY

            return enums.NEEDS_CLEANUP

        if self.status == enums.NEEDS_SPLIT:
            return enums.SPLITTING

        if self.status == enums.SPLITTING:
            if not self.has_flag(TrackFlags.SKIP_REKEY):
                return enums.NEEDS_REKEY

            return enums.NEEDS_CLEANUP

        if self.status == enums.NEEDS_REKEY:
            return enums.REKEYING

        if self.status == enums.REKEYING:
            return enums.NEEDS_CLEANUP

        if self.status == enums.NEEDS_CLEANUP:
            return enums.CLEANING_UP

        if self.status == enums.CLEANING_UP:
            return enums.DONE

    def serial(self):
        data = primitives(self.__data__)
        data.update(dict(
            status_name=status_name(self.status),
        ))
        return data

    def __str__(self):
        return "{} ({})".format(self.title, self.get_id())

    def has_flag(self, flag):
        return bool(self.flags & flag.value)


class TrackFile(BaseModel):
    track = ForeignKeyField(Track)
    key_offset = IntegerField(default=0)
    file_type = EnumField(FileType)
    file_url = CharField(null=True)
    status = EnumField(FileStatus)
    uuid = UUIDField(default=uuid4())
    error_message = CharField(null=True)

    def serial(self):
        data = primitives(self.__data__)
        data.update(dict(
            status_name=status_name(self.status),
            key_offset=signed(self.key_offset),
            key=offset_key(self.track.key, self.key_offset) + " " + self.track.quality,
            file_name=self.nice_name(),
            type_name=self.file_type.name
        ))
        return data

    def __repr__(self):
        return "{} ({})".format(signed(self.key_offset), self.id)

    @property
    def status_enum(self):
        return FileStatus

    @property
    def error_status(self):
        return FileStatus.ERROR

    def set_status(self, status):
        self.status = status
        self.save()

    def expect_status(self, status):
        if not self.is_status(status):
            raise ValueError('Expected status {} but got {}', status, self.status)

    def is_status(self, status):
        if not isinstance(status, list):
            status = [status]
        return self.status in status

    def is_type(self, file_types):
        if not isinstance(file_types, list):
            file_types = [file_types]
        return self.file_type in file_types

    @staticmethod
    def prepare(track, offsets, do_splits):
        keys = []
        i = 0
        split = 0
        normal = 1

        for offset in offsets:
            i += 1
            keys.append((
                i, normal,
                key_for(TrackFile.prep_file(track, offset, FileType.NORMAL_AUDIO))
            ))

            if do_splits:
                keys.append((
                    i, split,
                    key_for(TrackFile.prep_file(track, offset, FileType.INSTRUMENTAL_AUDIO))
                ))

        if track.has_flag(TrackFlags.NOVOX_FIRST):
            keys = sorted(keys, key=lambda k: (k[1], k[0]))
        return [k[2] for k in keys]

    @staticmethod
    def prep_file(track, offset, file_type):
        try:
            track_file = TrackFile.get(
                TrackFile.track == track,
                TrackFile.key_offset == offset,
                TrackFile.file_type == file_type
            )
            track_file.set_status(FileStatus.QUEUED)
            track_file.save()
            return track_file
        except TrackFile.DoesNotExist:
            pass

        track_file = TrackFile(
            track=track,
            key_offset=offset,
            file_type=file_type,
            status=FileStatus.QUEUED
        )

        track_file.save()
        return track_file

    def next_status(self):
        status = self._next_status()
        if status and status != self.status:
            self.set_status(status)

    def _next_status(self):
        if self.status == FileStatus.QUEUED:
            return FileStatus.WORKING

        if self.status == FileStatus.WORKING:
            return FileStatus.NEEDS_ENCODING

        if self.status == FileStatus.ENCODING:
            return FileStatus.NEEDS_UPLOAD

        if self.status == FileStatus.UPLOADING:
            return FileStatus.DONE

    def nice_title(self):
        pad_id = f'000{self.id}'[-3:]
        title = self.track.title.lower()
        for char in ["'", "/"]:
            title = title.replace(char, '')
        title = re.sub('[^a-z0-1\\-\\ ]+.*$', '', title)
        title = title.strip(' ').replace(' ', '-')
        title = re.sub('-+', '-', title)
        return title or pad_id

    def nice_name(self, ext=None):
        ext = ext or ext_for(self.file_type)
        if not ext:
            logger.warn(f"No ext for file id {self.id}")
            ext = 'mp3'

        nice_key = self.nice_key()
        nice_title = self.nice_title()
        vox = ""
        if self.is_type([FileType.INSTRUMENTAL_AUDIO, FileType.INSTRUMENTAL_VIDEO]):
            vox = "-noVocal"

        return f'{nice_key}{vox}-{nice_title}.{self.id}.{ext}'

    def nice_key(self):
        key = offset_key(self.track.key, self.key_offset).replace('b', 'flat').replace('#', 'sharp')
        minor = ''
        if self.track.quality != 'major':
            minor = 'm'

        return f'{key}{minor}'

    def public_url(self, ext=None):
        name = self.nice_name(ext)
        return f'https://s3.amazonaws.com/{S3_BUCKET}/{name}'


def files_for(track: Track):
    files = [t for t in TrackFile.select().where(TrackFile.track == track).order_by(TrackFile.key_offset)]
    return files


def files_data_for(track: Track):
    files = files_for(track)
    return [track_file.serial() for track_file in files]


def queue_encode(track_file, audio, red):
    track_file.set_status(FileStatus.NEEDS_ENCODING)
    red.rpush(Queue.ENCODE.value, key_for(track_file, audio))


def queue_upload(track_file, audio, red):
    track_file.set_status(FileStatus.NEEDS_UPLOAD)
    red.rpush(Queue.UPLOAD.value, key_for(track_file, audio))


def queue_cleanup(track, red):
    track.set_status(TrackStatus.NEEDS_CLEANUP)
    red.rpush(Queue.CLEANUP.value, key_for(track))


def cleanup_check(track, red):
    tracks = TrackFile.select().where(
        TrackFile.track == track
    )

    tracks = [t for t in tracks]
    kept = [t for t in tracks if not t.is_status([FileStatus.DONE, FileStatus.ERROR])]
    track_count = len(kept)

    if track_count == 0:
        queue_cleanup(track, red)


if mktables:
    logger.info("making tables")
    db.connect()
    db.create_tables([User, Track, TrackFile], safe=True)
    db.close()
