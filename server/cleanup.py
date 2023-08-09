#!/usr/bin/env python
import os

from server.consts import YTDLP_OUTPUT_DIR, SPLEETER_OUTPUT_DIR, RUBBERBAND_OUTPUT_DIR, KEYDETECT_OUTPUT_DIR
from server.db import Queue, Track, TrackStatus, TrackFile
from server.log import logger
from server.task import Task


class CleanupTask(Task):
    def __init__(self):
        super(CleanupTask, self).__init__(Queue.CLEANUP.value, Track)

    def work(self, track: Track, opts):
        # track.expect_status([TrackStatus.NEEDS_CLEANUP, TrackStatus.CLEANING_UP])
        track.set_status(TrackStatus.CLEANING_UP)

        files = [
            (YTDLP_OUTPUT_DIR, f"{track.id}.info.json"),
            (YTDLP_OUTPUT_DIR, f"{track.id}.wav"),
            (SPLEETER_OUTPUT_DIR, str(track.id), 'accompaniment.wav'),
            (SPLEETER_OUTPUT_DIR, str(track.id), 'vocals.wav'),
            (SPLEETER_OUTPUT_DIR, str(track.id)),
            (KEYDETECT_OUTPUT_DIR, f"{track.id}.key.json")
        ]

        track_files = TrackFile.select().where(TrackFile.track == track)
        for track_file in track_files:
            for ext in ['mp3', 'wav']:
                nice_name = track_file.nice_name(ext=ext)
                files.append((RUBBERBAND_OUTPUT_DIR, nice_name))
                files.append((YTDLP_OUTPUT_DIR, nice_name))

        for path_parts in files:
            path = os.path.join(*path_parts)
            if os.path.isfile(path):
                try:
                    os.remove(path)
                    logger.info(f"Removed {path}")
                except Exception as e:
                    logger.warn(f"Can't remove {path}")
                    logger.exception(e)
                    pass
                continue

            if os.path.isdir(path) and len(path) > 10:
                try:
                    os.removedirs(path)
                    logger.info(f"Removed {path}")
                except Exception as e:
                    logger.warn(f"Can't remove {path}")
                    logger.exception(e)
                    pass
                continue

        if not track.is_status(TrackStatus.ERROR):
            track.set_status(TrackStatus.DONE)


if __name__ == '__main__':
    CleanupTask().watch()
