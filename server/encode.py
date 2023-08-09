#!/usr/bin/env python
import os

from ffmpeg import FFmpeg
from mutagen.easyid3 import EasyID3

from server.db import TrackFile, Queue, FileStatus, queue_upload
from server.log import logger
from server.task import Task
from server.util import assert_file


class EncodeTask(Task):
    def __init__(self):
        super(EncodeTask, self).__init__(Queue.ENCODE.value, TrackFile)

    def work(self, track_file: TrackFile, opts):
        # track_file.expect_status([FileStatus.NEEDS_ENCODING, FileStatus.ENCODING])
        track_file.set_status(FileStatus.ENCODING)
        audio = opts.pop(0)
        dir = os.path.dirname(audio)
        outfile = os.path.join(dir, track_file.nice_name())

        logger.info(f"ffmpeg -y -i {audio} {outfile}")
        ffmpeg = (
            FFmpeg()
            .option("y")
            .input(audio)
            .output(outfile)
        )

        ffmpeg.execute()
        assert_file(outfile)

        try:
            tags = EasyID3(outfile)
            nice_key = track_file.nice_key()
            tags["title"] = f"{nice_key} - {track_file.track.title}"
            tags.save()
        except Exception as e:
            logger.exception(e)
            pass

        queue_upload(track_file, outfile, self.redis)


if __name__ == '__main__':
    EncodeTask().watch()
