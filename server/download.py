#!/usr/bin/env python
import os

from server.consts import YTDLP_OUTPUT_DIR, YTDLP_IMAGE, DOCKER_USER
from server.db import Queue, Track, TrackStatus
from server.errs import JobError
from server.log import logger
from server.task import Task, volume


class DownloadTask(Task):
    def __init__(self):
        super(DownloadTask, self).__init__(Queue.DOWNLOAD.value, Track)

    def work(self, model: Track, opts):
        model.expect_status(TrackStatus.NEEDS_DOWNLOAD)
        model.set_status(TrackStatus.DOWNLOADING)

        outdir = "/output"
        cmd_fmt = "-x --no-overwrites --audio-format wav --audio-quality 0 -o {}/{}.wav '{}'"
        command = cmd_fmt.format(outdir, model.id, model.url)

        volumes = [
            volume(YTDLP_OUTPUT_DIR, outdir),
        ]

        logger.info("command: %s", command)
        self.docker.containers.run(YTDLP_IMAGE, command=command, remove=True, volumes=volumes, user=DOCKER_USER)

        outfile = os.path.join(YTDLP_OUTPUT_DIR, '{}.wav'.format(model.id))

        if not os.path.isfile(outfile):
            raise JobError('file not found: {}'.format(outfile))

        model.next_status(self.redis)


if __name__ == '__main__':
    DownloadTask().watch()
