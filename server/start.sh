#! /bin/bash
here=$(dirname $(readlink -f ${BASH_SOURCE[0]}))
export PYTHONPATH=$(dirname $here)

applog=/var/log/app.log
errlog=/var/log/error.log

runapp(){
  local app=${1}
  nohup ./${app} 2>${errlog} >${applog} &
}

runapp app.py
sleep 2

runapp metadata.py
runapp download.py
runapp keydetect.py
runapp spleet.py
runapp encode.py
runapp upload.py
runapp cleanup.py

runapp rubberband.py
runapp rubberband.py
runapp rubberband.py

exec tail -f $applog $errlog
