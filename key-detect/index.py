#!/usr/bin/env python
import json
import shutil
import sys
from datetime import datetime
from os import remove

import numpy as np
from essentia import Pool
from essentia.standard import (
    FrameGenerator,
    HPCP,
    Key,
    MonoLoader,
    SpectralPeaks,
    Spectrum,
    Windowing,
)

FRAME_SIZE = 2048
HOP_SIZE = 1024


def detect_key(audio):
    spec = Spectrum(size=FRAME_SIZE)
    spec_peaks = SpectralPeaks()
    hpcp = HPCP()
    key = Key(profileType="edma")
    w = Windowing(type="blackmanharris92")
    pool = Pool()

    for frame in FrameGenerator(audio, frameSize=FRAME_SIZE, hopSize=HOP_SIZE):
        frame_spectrum = spec(w(frame))
        frequencies, magnitudes = spec_peaks(frame_spectrum)
        hpcpValue = hpcp(frequencies, magnitudes)
        pool.add("hpcp", hpcpValue)

    hpcp_avg = np.average(pool["hpcp"], axis=0)
    detected_key, scale, _, _ = key(hpcp_avg)
    return detected_key, scale


def handler(filename):
    # Get the filename and file extension from the event
    extension = filename.split(".")[-1]

    # Write the file to a temporary location
    tmp_filename = "/tmp/input." + extension

    shutil.copy2(filename, tmp_filename)

    # Load the audio file, resampled to a 44.1kHz mono signal
    loader = MonoLoader(filename=tmp_filename, sampleRate=44100)
    audio = loader()

    # Detect the key and scale
    key, scale = detect_key(audio)

    data = {
        "key": key,
        "scale": scale,
        "filename": filename,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # delete the temporary file
    remove(tmp_filename)

    return json.dumps(data)


if __name__ == '__main__':
    args = [a for a in sys.argv]
    outfile = args.pop()
    infile = args.pop()
    with open(outfile, 'w') as f:
        f.write(handler(infile))
