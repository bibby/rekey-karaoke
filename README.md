# rekey-karaoke

A webpage interface and backend processing queue for transforming
a **youtube URL** of a song with instruments and voice(s) into
**instrumentals in all 12 keys**. This could be useful for singers, bands,
worship teams, and other vocal performers to generate practice tracks suited to
their range.

This is a personal toy project, and has no guarantee of quality or fitness for purpose.

---

## Setup

The intended deployment of this application is as a docker container that can start additional containers,
thus it is needed for `/var/run/docker.sock` to be volumed in (see `docker-compose.yml`).

Volumes on the docker host are used for temporary storage of process artifacts. Artifacts are ultimately
uploaded to S3 at a bucket you specify, but the temp storage is used to pass data between containers during the
processing steps,
and are cleaned up as a final step.

**Decide on a root volume.**

Edit `./build.sh` at the root of this repo and set your volume to the var `vol` (line 2). Part of the build
creates the necessary subdirectories that are owned by a non-root user. If the non-root user is not uid `1000`,
edit `./build.sh` line 22 to declare this.

### env file

Inspect `./server/consts.py` to see what other options are available for a configuration env file (see: `example.env`).
Minimally, your config file should include:

- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- S3_BUCKET
- DOCKER_USER (if other than 1000)

Edit `docker-compose.yml` to name your env file for config values.

## Process Steps

When a youtube url is supplied, it enters an initial queue and steps through the following processes:

- *MetaData* :  Gets song title, thumbnail, length, etc using
  image [thr3a/yt-dlp](https://hub.docker.com/r/thr3a/yt-dlp) or `YTDLP_IMAGE`
- *Download* : Initial audio fetched with image [thr3a/yt-dlp](https://hub.docker.com/r/thr3a/yt-dlp) or `YTDLP_IMAGE`
- *KeyDetect* : The original song key is detected/best-guessed with image sourced at `./key-detect`. This is a found
  script, whose original author I cannot locate at this time, but will try to attribute properly ASAP
- *Split* : Vocals get isolated and separated using image [deezer/spleeter](https://github.com/deezer/spleeter)
  or `SPLEETER_IMAGE`
- *ReKey* : Artifacts (Instrumentals AND Vocals) are transposed using the image sourced at `./rubber`, which is a light
  wrapper for the [rubber band pitch shifting lib](https://breakfastquay.com/rubberband/).
- *Encode* : wavs to mp3 with `ffmpeg`
- *Upload* : with `boto3`
- *Cleanup*

The web app uses the `peewee` ORM on a sqlite3 db, and uses tailwind and htmx .

# Auth

There is no auth. Auth is fake. This is a toy.

# Build

`./build.sh`

# Start

`docker-compose up -d`

# TODO

- Polls at regular intervals. Would prefer long polling.
- Processed audio could be stitched back onto the original video (like lyric videos), but video is currently ignored
- Actual auth might be nice.
- This could be a fun project to convert to AWS Lambda or other serverless/FaaS platform
