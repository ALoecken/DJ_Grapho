#!/usr/bin/env python3
#encoding: UTF-8

from fuzzywuzzy import fuzz
import json
import re
from unidecode import unidecode
import urllib.parse
import time
import random
import os

# for youtube (without api)
import urllib.request
from bs4 import BeautifulSoup

# for youtube 3 API
import googleapiclient.discovery
import google_auth_oauthlib.flow
import googleapiclient.errors

# to dave credentials
import pickle
import datetime


# needs to be downloaded from  https://console.developers.google.com/apis/api/youtube.googleapis.com/overview?project={{yourproject}}
YOUTUBE_CLIENT_SECRET = 'data/client_secret.json'
YOUTUBE_CREDENTIALS = 'data/cred.pickle'  # store the generated credetnials

JSON_PLAYLIST = 'data/songs.json'  # 'data/musthave.json'

_lastfm_lastreset = time.time()
_lastfm_counter = 0


def init_youtube():
    # Disable OAuthlib's HTTPS verification when running locally.
    # *DO NOT* leave this option enabled in production.
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    api_service_name = "youtube"
    api_version = "v3"
    client_secrets_file = YOUTUBE_CLIENT_SECRET
    scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
    credentials = None

    tries = 1
    while (tries > 0):
        try:
            with open(YOUTUBE_CREDENTIALS, 'rb') as f:
                credentials = pickle.load(f)
        except:
            print("some error while loading stored credentials")

        # Get credentials and create an API client
        if (credentials is None or credentials.expired or not credentials.valid):
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, scopes)
            credentials = flow.run_console()
            with open(YOUTUBE_CREDENTIALS, 'wb') as f:
                pickle.dump(credentials, f)
        try:
            youtube_api = googleapiclient.discovery.build(
                api_service_name, api_version, credentials=credentials)
            return youtube_api
        except: 
            # delete and try again
            os.remove(YOUTUBE_CREDENTIALS)
            tries = tries -1
    return None


def create_new_youtube_playlist(youtube_api, title, description):
    request = youtube_api.playlists().insert(
        part="snippet, status",
        body={
            "snippet": {
                "title": str(title),
                "description": str(description)
            },
            "status": {
                "privacyStatus": "unlisted"  # private public unlisted
            }
        }
    )
    response = request.execute()

    return response['id']


def add_video_to_playlist(youtube_api, playlist_id, video_id):

    request = youtube_api.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "position": 0,  # this makes it in reverse order!!
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
    )
    response = request.execute()


def ytTimeParser(duration_str):
    times = duration_str.split(':')
    if (len(times) == 1):  # only seconds
        return int(times[0])
    elif (len(times) == 2):  # min:sec
        return (int(times[0]) * 60) + int(times[1])
    elif (len(times) == 3):  # hrs:min:sec
        return (int(times[0]) * 1440) + (int(times[1]) * 60) + int(times[2])
    else:
        print("Currently, youtube only covers the format HH:MM:SS. This is not covered: " + duration_str)
        return None


def youtubeSearch(query, order):
    query_string = urllib.parse.urlencode({"search_query": query})
    html_content = urllib.request.urlopen(
        "http://www.youtube.com/results?" + query_string + "&sp=EgIQAQ%253D%253D" + "&" + order)
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


def getYoutubeLinkFromLastFM(trackinfo):
    global _lastfm_lastreset
    global _lastfm_counter
    try:
        url = "https://www.last.fm/music/" + \
            urllib.parse.quote(
                trackinfo['Artist']) + "/_/" + urllib.parse.quote(trackinfo['Title'])
        html_content = urllib.request.urlopen(url)
        soup = BeautifulSoup(html_content.read().decode(), 'html.parser')

        # note: only ask 5 times per seconds!!
        _lastfm_counter = _lastfm_counter + 1
        diff = float(time.time() - _lastfm_lastreset)
        if float(_lastfm_counter) / diff >= 5:
            wait = 1.0 + _lastfm_counter / (5.0 - diff)
            print("waiting " + str(wait) + "sec. for LastFM API")
            time.sleep(wait)
            _lastfm_counter = 0
            _lastfm_lastreset = time.time()

        for a in soup.find_all('a', class_='image-overlay-playlink-link'):
            trackinfo['VideoID'] = a.get('data-youtube-id')
            return trackinfo
    except:
        print("Could not get Youtube-ID for " +
              str(trackinfo) + " from LastFM")
        return None


def getYoutubeLink(trackinfo, round=0):
    # TODO this should not happen!!
    if trackinfo is None:
        return None

    # check lastfm first:
    if (round <= 0):
        v = getYoutubeLinkFromLastFM(trackinfo)
        if not (not v or v.get('VideoID') is None):
            return v

    if round > 31:
        return None

    if round % 2 == 0:
        #order = "viewCount"
        order = 'sp=CAM%253D'
    else:
        #order = "relevance"
        order = "sp=CAA%253D"

    if int(round / 2) % 2 == 0:
        spoti = False
    else:
        spoti = True

    if int(round / 4) % 2 == 0:
        inQuotes = False
    else:
        inQuotes = True

    if int(round / 8) % 2 == 0:
        decoded = False
    else:
        decoded = True

    if int(round / 16) % 2 == 0:
        removeBrackets = False
    else:
        removeBrackets = True

    if spoti:
        if 'ArtistSpoty' in trackinfo and 'TitleSpoty' in trackinfo:
            a = trackinfo['ArtistSpoty']
            t = trackinfo["TitleSpoty"]
        else:
            return getYoutubeLink(trackinfo, round + 1)
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
             'VideoTitle': search_result['title'],
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
                or '8 bit' in title \
                or fuzz.partial_ratio(t.lower(), title) < 80:
            # not trackinfo['Title'].lower() in title:
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
            # abs(durationInTInfo - duration) <= 30:
            return bestV

    # 2nd try all videos
    for v in videos:
        duration = v['Duration']
        # no duration info. Get no songs longer than 15min!
        if duration < 1000 and (
            (durationInTInfo is None or durationInTInfo <= 0)
                or durationInTInfo / duration > .85 and durationInTInfo / duration < 1.15):
            # abs(durationInTInfo - duration) <= 30:
            return v

    # did not find anything
    return getYoutubeLink(trackinfo, round=round + 1)


if __name__ == "__main__":
    # load generated JSON playlist
    with open(JSON_PLAYLIST) as json_data:
        musiclist = json.load(json_data)
        musiclist = musiclist[::-1]  # reverse (videos are "stacked" later)

    # -1: get csv path
    title = input("Please enter the title of your playlist: ")
    description = input("Please enter the description for your playlist: ")

    # 0. init youtube --> do it later to see if everything else worked first!
    yAPI = None  # init_youtube()
    playlist_id = None  # create_new_youtube_playlist(yAPI)

    lastsleep = time.time()
    for i, item in enumerate(musiclist):
        # sleep --> don't ask youtube too many questions at once
        if (time.time() - lastsleep < .333):
            time.sleep(
                max(.001, (random.random() / 3.) + .333 - (time.time() - lastsleep)))
            lastsleep = time.time()

        video = getYoutubeLink(item)
        if video is not None:
            for k, v in video.items():
                item[k] = v

            # 3. use youtube API to create a new playlist with the found IDs
            # based on https://developers.google.com/youtube/v3/code_samples/code_snippets?apix=true
            if (yAPI is None):
                yAPI = init_youtube()
                playlist_id = create_new_youtube_playlist(yAPI, title, description)
            add_video_to_playlist(yAPI, playlist_id, item['VideoID'])
            print(item)
        else:
            print('Could not find video: %s' % str(item))
