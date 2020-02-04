#!/usr/bin/env python2
#encoding: UTF-8

import json
import os
import time
from unidecode import unidecode

PATH_TO_MP3S = 'E:/TMP/MP3/'
JSON_PLAYLIST = 'data/songs.json' # 'data/musthave.json'

## this goes through the provided playlist and converts it to an m3u playlist, based on existing mp3s in the provided PATH_TO_MP3S
# TODO: PATH_TO_MP3S and JSON_PLAYLIST as command line args

if __name__ == "__main__":
    with open(JSON_PLAYLIST, 'r') as json_data:
        musiclist = json.load(json_data)

    with open(PATH_TO_MP3S + 'long' + str(time.time()) + '.m3u', 'w') as flong:
        for data in musiclist:
            if data is not None:  # TODO should not happen!
                filename = unidecode(data['Artist'] + " - " + data["Title"])
                print(filename)
                for file in os.listdir(PATH_TO_MP3S):
                    if str(file).lower().startswith(filename.lower()):
                        flong.write(PATH_TO_MP3S + str(file) + '\n')
