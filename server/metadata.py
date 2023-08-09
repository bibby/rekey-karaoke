#!/usr/bin/env python
import os
from pathlib import Path

from urllib3.util import parse_url

from server.consts import YTDLP_OUTPUT_DIR, YTDLP_IMAGE, DOCKER_USER
from server.db import Queue, Track, TrackStatus
from server.log import logger
from server.task import Task, volume, read_json


class MetadataTask(Task):
    def __init__(self):
        super(MetadataTask, self).__init__(Queue.METADATA.value, Track)

    def work(self, model: Track, opts):
        # model.expect_status(TrackStatus.NEEDS_METADATA)
        model.set_status(TrackStatus.GETTING_METADATA)

        outdir = "/output"
        command = "--write-info-json --no-download --force-overwrites -o {}/{} '{}'".format(outdir, model.id, model.url)

        volumes = [
            volume(YTDLP_OUTPUT_DIR, outdir),
        ]

        logger.info("command: %s", command)
        self.docker.containers.run(YTDLP_IMAGE, command=command, remove=True, volumes=volumes, user=DOCKER_USER)

        outfile = os.path.join(YTDLP_OUTPUT_DIR, '{}.info.json'.format(model.id))

        data = read_json(outfile)
        model.title = data.get('title')
        model.thumbnail = get_thumb(data.get("thumbnails"))
        model.duration = data.get('duration_string', 'unknown')
        model.save()

        if data.get('duration', 0) >= 15 * 60:
            model.set_status(TrackStatus.REJECTED)
        else:
            model.next_status(self.redis)


def get_thumb(thumbs):
    return _get_thumb(thumbs, 180, 320, '.jpg') or \
           _get_thumb(thumbs, 188, 336, '.jpg') or \
           _get_thumb(thumbs, 360, 480, '.jpg') or \
           _get_thumb(thumbs, 480, 640, '.jpg')


def _get_thumb(thumbs, height, width, ext):
    for thumb in thumbs:
        if thumb.get('height') != height:
            continue

        if thumb.get('width') != width:
            continue

        url = thumb.get('url')
        if Path(parse_url(url).path).suffix != ext:
            continue

        return url


if __name__ == '__main__':
    MetadataTask().watch()
