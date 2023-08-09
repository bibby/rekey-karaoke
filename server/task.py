import json
import os
import time
from abc import ABC, abstractmethod

import docker
from redis.client import StrictRedis

from server.consts import REDIS_HOST
from server.errs import JobError
from server.log import logger
from server.util import unkey


class Task(ABC):

    def __init__(self, channel, model):
        self.channel = channel
        self.model = model
        self.docker = docker.from_env()
        self.redis = StrictRedis(host=REDIS_HOST)

    def watch(self):
        while True:
            time.sleep(1)
            key: bytes = self.redis.lpop(self.channel)
            if not key:
                continue

            try:
                obj, opts = self.find(key.decode('utf-8'))
                self.start(obj, opts)
            except JobError as e:
                logger.exception(e)

    def find(self, key):
        parts = unkey(key)
        model_name = parts.pop(0)
        model = self.model
        expected_name = model.__name__
        if model_name != expected_name:
            raise JobError('Expected {}. Got {}'.format(expected_name, model_name))

        id = parts.pop(0)
        if not id:
            raise JobError('Expected id. Got {}'.format(id))
        try:
            return model.get(int(id)), parts
        except model.DoesNotExist:
            raise JobError('Model not found: {} {}'.format(model, id))

    def start(self, model, opts=None):
        try:
            self.work(model, opts)
        except Exception as e:
            logger.exception(e)
            model.error_message = str(e)
            model.set_status(model.error_status)

    @abstractmethod
    def work(self, model, opts):
        pass


def volume(host_path, container_path):
    return ':'.join([host_path, container_path])


def read_json(json_file):
    if not os.path.isfile(json_file):
        raise JobError('file not found: {}'.format(json_file))

    with(open(json_file, 'r') as f):
        data = json.load(f)

    return data
