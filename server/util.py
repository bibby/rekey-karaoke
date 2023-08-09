import json
import os
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID

from peewee import Model

from server.consts import REDIS_KEY_SEPERATOR


def serial(data, depth=0, raw=False):
    output = None
    if isinstance(data, list):
        output = [
            serial(item, depth=depth + 1) for
            item in data
        ]

    elif isinstance(data, tuple):
        output = tuple([
            serial(item, depth=depth + 1) for
            item in data
        ])

    elif isinstance(data, Model):
        output = data.serial()

    elif isinstance(data, datetime):
        return primitive(data)

    elif isinstance(data, timedelta):
        minutes = ("00" + str(data.seconds // 60))[-2:]
        seconds = ("00" + str(data.seconds % 60))[-2:]
        return f'{minutes}:{seconds}'

    if depth == 0 and not raw:
        return json.dumps(output)
    else:
        return output


def primitives(data):
    return {key: primitive(value) for key, value in data.items()}


def primitive(value):
    if value is None:
        return ""

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, datetime):
        return value.strftime("%b %d %Y %H:%M:%S")

    if isinstance(value, UUID):
        return str(value)

    return value


def key_for(model, *args):
    return make_key(model.__class__.__name__, str(model.get_id()), *args)


def make_key(*args):
    return REDIS_KEY_SEPERATOR.join(map(str, args))


def unkey(key):
    return key.split(REDIS_KEY_SEPERATOR)


def signed(num):
    if num <= 0:
        return str(num)
    return f"+{num}"


def fix_key(key):
    keymap = {
        'A#': 'Bb',
        'C#': 'Db',
        'D#': 'Eb',
        'G#': 'Ab',
        'Gb': 'F#',
    }

    return keymap.get(key, key)


def offset_key(key, offset):
    keymap = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
    if key not in keymap:
        raise ValueError(f'unfixed key: {key}')

    if offset == 0:
        return key

    while keymap[0] != key:
        list_right(keymap)

    if offset < 0:
        while offset < 0:
            list_left(keymap)
            offset += 1
        return keymap[0]

    while offset > 0:
        list_right(keymap)
        offset -= 1
    return keymap[0]


def list_left(lst):
    lst.insert(0, lst.pop())


def list_right(lst):
    lst.append(lst.pop(0))


def assert_file(filename):
    if not os.path.isfile(filename):
        raise FileNotFoundError(filename)
