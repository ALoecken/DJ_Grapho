#!/usr/bin/env python3
#encoding: UTF-8

from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
import json
import re
from unidecode import unidecode
import urllib.parse
import urllib.request
import youtube_dl

PATH_TO_MP3S = 'E:/TMP/MP3/'
JSON_PLAYLIST = 'data/songs.json' # 'data/musthave.json'

def ytTimeParser(duration_str):
    times = duration_str.split(':')
    if (len(times) == 1): # only seconds
        return int(times[0])
    elif (len(times) == 2): # min:sec
        return (int(times[0]) * 60) + int(times[1])
    elif (len(times) == 3): # hrs:min:sec
        return (int(times[0]) * 1440) + (int(times[1]) * 60) + int(times[2])
    else:
        print ("Currently, youtube only covers the format HH:MM:SS. This is not covered: " + duration_str)
        return None

def youtubeSearch(query, order):
    query_string = urllib.parse.urlencode({"search_query": query})
    html_content = urllib.request.urlopen("http://www.youtube.com/results?" + query_string + "&sp=EgIQAQ%253D%253D" + "&" + order)
    soup = BeautifulSoup(html_content.read().decode(), 'html.parser')
        
    results = []
    for container in soup.find_all('div', class_='yt-lockup-content'):
        result = {}
        
        # chanel name
        result['channelTitle'] = ''
        for channel in container.find_all('div', class_='yt-lockup-byline'):
            result['channelTitle'] = channel.a.get_text()
        
        # description
        result['description'] = ''
        for descr in container.find_all('div', class_='yt-lockup-description'):
            result['description'] = descr.get_text()
        
        # rest
        result['title'] = container.h3.a.get_text()
        result['id'] = container.h3.a.get('href')[9:]
        result['duration'] = ytTimeParser(container.h3.span.get_text()[10:])
        results.append(result)
        
    return results

def getYoutubeLink(trackinfo, round=0):
    # TODO this should not happen!!
    if trackinfo is None: 
        return None

    if round > 31: 
        return None

    if round % 2 == 0: 
        #order = "viewCount"
        order = 'sp=CAM%253D'
    else: 
        #order = "relevance"
        order = "sp=CAA%253D"
    
    if int(round / 2) % 2 == 0: spoti = False
    else: spoti = True
    
    if int(round / 4) % 2 == 0: inQuotes = False
    else: inQuotes = True
    
    if int(round / 8) % 2 == 0: decoded = False
    else: decoded = True
    
    if int(round / 16) % 2 == 0: removeBrackets = False
    else: removeBrackets = True

    if spoti:
        if 'ArtistSpoty' in trackinfo and  'TitleSpoty' in trackinfo:
            a = trackinfo['ArtistSpoty']
            t = trackinfo["TitleSpoty"]
        else: return getYoutubeLink(trackinfo, round + 1)
    else:
        a = trackinfo['Artist']
        t = trackinfo["Title"]
    
    if removeBrackets:
        a = re.sub(r'\([^)]*\)', '', a)
        t = re.sub(r'\([^)]*\)', '', t)
        
    if decoded:
        a = unidecode(a)
        t = unidecode(t)
    
    if inQuotes:
        a = '"%s"' % a
        t = '"%s"' % t
    
    query = '"%s" "%s"' % (a, t)
    
    # Call the search.list method to retrieve results matching the specified
    # query term.
    
    search_response = youtubeSearch(query, order)
    
    videos = []
    bestmatch = [] 
    
    # Add each result to the appropriate list, and then display the lists of
    # matching videos, channels, and playlists.
    for search_result in search_response:
        r = {'VideoID': search_result['id'], 
             'VideoTitle':search_result['title'],
             'Duration': search_result['duration']}
        title = search_result['title'].lower()
        descr = search_result['description'].lower()
        channel = search_result['channelTitle'].lower()
        # TODO: what if remix or cover is part of the title name ?
        if 'remix' in descr \
            or 'remix' in title \
            or 'review' in descr \
            or 'review' in title \
            or 'karaoke' in descr \
            or 'karaoke' in title  \
            or 'karaoke' in channel \
            or 'zuruixk' in channel \
            or fuzz.partial_ratio(t.lower(), title) < 80: 
            #not trackinfo['Title'].lower() in title:
            continue 

        videos.append(r)
        if 'official' in title \
            or 'official' in channel \
            or 'offiziell' in title \
            or 'offiziell' in channel \
            or 'records' in channel \
            or 'limpbizkit' in channel \
            or 'muse' in channel \
            or 'bliss corporation' in channel \
            or 'vevo' in channel \
            or 'musicalsrmything' in channel \
            or 'laserkraft' in channel \
            or 'jonlajoie' in channel \
            or "rock 'n' roll realschule" in descr \
            or 'bademeistertv' in channel \
            or 'classik k' in channel:
            bestmatch.append(r)
    
    # TODO: what if spotify's estimation of duration is wrong
    durationInTInfo = None
    if ('DurationSpoty' in trackinfo and trackinfo['DurationSpoty'] is not None and trackinfo['DurationSpoty'] > 0):
        durationInTInfo = trackinfo['DurationSpoty']
    elif ('Duration' in trackinfo and trackinfo['Duration'] is not None and trackinfo['Duration'] > 0):
        durationInTInfo = trackinfo['Duration']
    
    # 1st try best videos
    for bestV in bestmatch:
        duration = bestV['Duration']
        # no duration info. Get no songs longer than 15min!
        if duration < 1000 and (
                                (durationInTInfo is None or durationInTInfo <= 0)
                                or durationInTInfo / duration > .85 and durationInTInfo / duration < 1.15):
            #abs(durationInTInfo - duration) <= 30:
            return bestV
    
    # 2nd try all videos
    for v in videos:
        duration = v['Duration']
        # no duration info. Get no songs longer than 15min!
        if duration < 1000 and (
                                (durationInTInfo is None or durationInTInfo <= 0)
                                or durationInTInfo / duration > .85 and durationInTInfo / duration < 1.15):
            #abs(durationInTInfo - duration) <= 30:
            return v
        
    # did not find anything   
    return getYoutubeLink(trackinfo, round=round + 1)
    
        
if __name__ == "__main__":
    #with open('musthave.json') as json_data:
    with open(JSON_PLAYLIST) as json_data:
    #with open('important.json') as json_data:
        musiclist = json.load(json_data)
    
    #path = 'F:/TMP/YoutubeVideo/' 
    for i, item in enumerate(musiclist): 
        video = getYoutubeLink(item)
        if video is not None:
            for k, v in video.items():
                item[k] = v
            item['pos'] = i
            url = "http://www.youtube.com/watch?v=%s" % item['VideoID']
            print(url)
            filename = unidecode(item['Artist'] + " - " + item["Title"])
            #ydl_opts = {'format': 'bestvideo[height<=1050]+bestaudio/best[height<=1050]/best', # merge best video and audio
            ydl_opts = {'format': 'bestaudio/best', # only audio
                'outtmpl': PATH_TO_MP3S + filename + '.%(ext)s',
                'download_archive': PATH_TO_MP3S + 'downloaded_songs.txt',
                # for audio extraction:
                #'keepvideo': True,
                'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '245'              
                }]
                ,
                # this only writes to m4a. mp3 bug?
                'postprocessor_args': ['-metadata', 'title=' + item['Title'],
                    '-metadata', 'album=' + (item['Album'] if 'Album' in item else ''), 
                    '-metadata', 'artist=' + item['Artist'],
                    '-metadata', 'youtube=' + url 
                ]# '-af', 'volume=5dB'
                }
            try: 
                with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as ex:
                print ('Could not download %s: %s' % (filename, ex))
        else:
            #print ("Could find video for %s: %s" % (item['Artist'], item['Title'] ))
            print ('Could not find video: %s' % str(item))