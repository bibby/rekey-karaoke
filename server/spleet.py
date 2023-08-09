#!/usr/bin/env python
import os

from log import logger
from server.consts import SPLEETER_IMAGE, SPLEETER_INPUT_DIR, SPLEETER_OUTPUT_DIR, ORIGINAL_KEY, DOCKER_USER
from server.db import Track, Queue, TrackStatus, queue_encode, TrackFile, FileType
from server.task import Task, volume
from server.util import assert_file


class SpleetTask(Task):
    def __init__(self):
        super(SpleetTask, self).__init__(Queue.SPLIT.value, Track)

    def work(self, model: Track, opts):
        # model.expect_status(TrackStatus.NEEDS_SPLIT)
        model.set_status(TrackStatus.SPLITTING)

        logger.info("Starting spleet: %s", model.title)

        input_dir = "/input"
        output_dir = "/output"

        volumes = [
            volume(SPLEETER_INPUT_DIR, input_dir),
            volume(SPLEETER_OUTPUT_DIR, output_dir),
        ]

        basename = '{}.wav'.format(model.id)
        in_file = os.path.join(SPLEETER_INPUT_DIR, basename)
        assert_file(in_file)

        command = "separate -o {} {}/{}".format(output_dir, input_dir, basename)
        logger.info("command: %s", command)
        self.docker.containers.run(
            SPLEETER_IMAGE,
            command=command,
            remove=True,
            volumes=volumes,
            # user=DOCKER_USER
        )

        # vocal only
        # os.path.join(SPLEETER_OUTPUT_DIR, model.id, 'vocals.wav'),

        outfile = os.path.join(SPLEETER_OUTPUT_DIR, str(model.id), 'accompaniment.wav')
        assert_file(outfile)

        spleet_dir = os.path.join(SPLEETER_OUTPUT_DIR, str(model.id))
        try:
            self.docker.containers.run(
                "alpine",
                command=f"chown -R {DOCKER_USER}:{DOCKER_USER} /input",
                tty=True,
                remove=True,
                volumes=[
                    f"{spleet_dir}:/input"
                ],
            )
        except Exception as e:
            logger.exception(e)
            pass

        track_file = TrackFile.prep_file(model, ORIGINAL_KEY, FileType.INSTRUMENTAL_AUDIO)
        queue_encode(track_file, outfile, self.redis)
        model.next_status(self.redis)


if __name__ == '__main__':
    SpleetTask().watch()
