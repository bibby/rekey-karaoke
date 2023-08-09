#!/usr/bin/env python
import os

from server.consts import KEYDETECT_IMAGE, KEYDETECT_INPUT_DIR, KEYDETECT_OUTPUT_DIR, ORIGINAL_KEY, DOCKER_USER
from server.db import Queue, Track, TrackStatus, queue_encode, TrackFile, FileType
from server.log import logger
from server.task import Task, volume, read_json
from server.util import fix_key, assert_file


class KeyTask(Task):
    def __init__(self):
        super(KeyTask, self).__init__(Queue.KEY_DETECT.value, Track)

    def work(self, model: Track, opts):
        # model.expect_status(TrackStatus.NEEDS_KEYDETECT)
        model.set_status(TrackStatus.GETTING_KEY)

        logger.info("Starting key-detect: %s", model.title)

        input_dir = "/input"
        output_dir = "/output"

        volumes = [
            volume(KEYDETECT_INPUT_DIR, input_dir),
            volume(KEYDETECT_OUTPUT_DIR, output_dir),
        ]

        in_file = os.path.join(KEYDETECT_INPUT_DIR, f'{model.id}.wav')
        assert_file(in_file)

        command = f"{input_dir}/{model.id}.wav {output_dir}/{model.id}.key.json"
        logger.info("command: %s", command)
        self.docker.containers.run(KEYDETECT_IMAGE, command=command, remove=True, volumes=volumes, user=DOCKER_USER)

        outfile = os.path.join(KEYDETECT_OUTPUT_DIR, '{}.key.json'.format(model.id))

        data = read_json(outfile)
        model.key = fix_key(data.get('key'))
        model.quality = data.get('scale')
        model.save()

        track_file = TrackFile.prep_file(model, ORIGINAL_KEY, FileType.NORMAL_AUDIO)
        queue_encode(track_file, in_file, self.redis)

        model.next_status(self.redis)


if __name__ == '__main__':
    KeyTask().watch()
