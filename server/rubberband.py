#!/usr/bin/env python
import os

from server.consts import RUBBERBAND_INPUT_DIR, RUBBERBAND_OUTPUT_DIR, RUBBERBAND_IMAGE, RUBBERBAND_SPLITS_DIR, DOCKER_USER
from server.db import Queue, TrackStatus, queue_encode, TrackFile, FileStatus, FileType
from server.log import logger
from server.task import Task, volume
from server.util import assert_file


class RubberbandTask(Task):
    def __init__(self):
        super(RubberbandTask, self).__init__(Queue.REKEY.value, TrackFile)

    def work(self, track_file: TrackFile, opts):
        track = track_file.track
        track.expect_status([TrackStatus.NEEDS_REKEY, TrackStatus.REKEYING])
        track_file.track.set_status(TrackStatus.REKEYING)
        track_file.set_status(FileStatus.WORKING)

        logger.info("Starting rubberband: %s", track.title)

        input_dir = "/input"
        output_dir = "/output"

        if track_file.is_type([FileType.INSTRUMENTAL_AUDIO, FileType.INSTRUMENTAL_VIDEO]):
            input_src = RUBBERBAND_SPLITS_DIR
            input_file = f"{track_file.track.id}/accompaniment.wav"
        else:
            input_src = RUBBERBAND_INPUT_DIR
            input_file = f"{track_file.track.id}.wav"

        volumes = [
            volume(input_src, input_dir),
            volume(RUBBERBAND_OUTPUT_DIR, output_dir),
        ]

        in_file = os.path.join(input_src, input_file)
        assert_file(in_file)

        offset = track_file.key_offset
        out_base = track_file.nice_name(ext='wav')

        command = f"'{offset}' {input_dir}/{input_file} {output_dir}/{out_base}"
        logger.info("command: %s", command)
        self.docker.containers.run(RUBBERBAND_IMAGE, command=command, remove=True, volumes=volumes, user=DOCKER_USER)

        outfile = os.path.join(RUBBERBAND_OUTPUT_DIR, out_base)
        queue_encode(track_file, outfile, self.redis)


if __name__ == '__main__':
    RubberbandTask().watch()
