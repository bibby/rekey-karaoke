#!/usr/bin/env python
import boto3
from botocore.exceptions import ClientError

from server.consts import S3_BUCKET
from server.db import Queue, TrackFile, FileStatus, cleanup_check, TrackStatus, TrackFlags
from server.log import logger
from server.task import Task
from server.util import assert_file


class UploadTask(Task):
    def __init__(self):
        super(UploadTask, self).__init__(Queue.UPLOAD.value, TrackFile)

    def work(self, track_file: TrackFile, opts):
        track_file.expect_status([FileStatus.NEEDS_UPLOAD, FileStatus.UPLOADING])
        track_file.set_status(FileStatus.UPLOADING)
        audio = opts.pop(0)
        assert_file(audio)

        bucket = S3_BUCKET
        nice_name = track_file.nice_name()

        try:
            s3_client = boto3.client('s3')
            s3_client.upload_file(audio, bucket, nice_name)
            track_file.file_url = track_file.public_url('mp3')
            track_file.save()
            track_file.next_status()

        except ClientError as e:
            logger.exception(e)
            raise

        track = track_file.track
        is_rekey = track.is_status(TrackStatus.REKEYING)
        is_split = track.is_status(TrackStatus.SPLITTING)
        is_keying = track.is_status(TrackStatus.GETTING_KEY)
        skip_rekey = track.has_flag(TrackFlags.SKIP_REKEY)
        skip_split = track.has_flag(TrackFlags.SKIP_SPLIT)

        check_conditions = [
            is_rekey,
            is_split and skip_rekey,
            is_keying and skip_rekey and skip_split,
        ]
        logger.info(check_conditions)
        if any(check_conditions):
            cleanup_check(track_file.track, self.redis)


if __name__ == '__main__':
    UploadTask().watch()
