#!/usr/bin/env python3
#encoding: UTF-8

import json

if __name__ == "__main__":
    #with open('musthave.json') as json_data:
    with open('data/songs.json') as json_data:
    #with open('important.json') as json_data:
        musiclist = json.load(json_data)
    
    playlistItems = []
    for i, item in enumerate(musiclist): 
        print (item['Artist']  + " - " + item["Title"]) 
