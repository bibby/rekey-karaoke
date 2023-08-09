#!/bin/bash

pitch=${1}
in_id=${2}
out_id=${3}

# echo rubberband -3 -p "'${pitch}'" /opt/in/${in_id}.wav /opt/out/${out_id}.wav
rubberband -3 -p "${pitch}" "${in_id}" "${out_id}"
