#!/bin/bash
set -e
vol=/opt/volumes/split
here=$(dirname $(readlink -f ${BASH_SOURCE[0]}))

build(){
  cd ${here}
  cd ${1}
  ./build.sh
}

build key-detect
build rubber
build server

docker pull thr3a/yt-dlp
docker pull deezer/spleeter:3.8-2stems

mkvol(){
  echo "mkdir ${1}" >&2
  sudo mkdir -p "${1}"
  sudo chown -R 1000:1000 "${1}"
}

mkvol "${vol}"
for dir in keydetect rubberband spleets ytdlp
do
  mkvol "${vol}/${dir}"
done

