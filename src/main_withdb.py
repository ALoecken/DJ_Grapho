#!/usr/bin/env python3
#encoding: UTF-8

# Usage: run this first
# Then youtube_downloader.py
# Then playlistgenerator.py

import concurrent.futures
import json
# WARNING: NEEDS TOD BE BELOW v2 (e.g., 1.11: pip install networkx==1.11)
import networkx as nx
from random import shuffle
import re
import requests
import sqlite3
import sys
import time
from urllib.parse import quote
import csv


_SECRETS_FILE = "data/mysecrets.json"


class GraphCreator:

    @staticmethod
    def createID(artist, title):
        id = (artist + ' - ' + title).lower()
        id = re.sub(r'\W+', '', id)
        return id

    ##
    def getSpotifyTracks(self, playlistid):
        db = self.getDBCursor()
        conn = db['conn']
        c = db['cursor']

        offset = 0
        i = 0
        result = list()

        while True:
            response = requests.get('https://api.spotify.com/v1/users/' + self.spoti_user + '/playlists/' + playlistid + "/tracks?limit=100&offset=" + str(offset),
                                    headers={'Authorization': 'Bearer ' + self.spoti_user_token, "Accept": "application/json"})
            json = response.json()
            tracks = json['items']

            tobecorrected = list()
            for track in tracks:
                i += 1
                # todo: also add other artists?
                title = track['track']['name'].split(
                    ' - ')[0].split(' (')[0].strip()
                artist = track['track']['artists'][0]['name'].strip()
                key = self.createID(artist, title)

                # skip if already
                c.execute(
                    'SELECT count(id) FROM spotify WHERE oldid = ? ', (key, ))
                row = c.fetchone()
                if row[0] <= 0:
                    tobecorrected.append(
                        {'Pos': i,
                         'TitleSpoty': title,
                         'AlbumSpoty': track['track']['album']['name'],
                         'ArtistSpoty': artist,
                         'IDSpoty': key,
                         'Title': title,
                         'Album': track['track']['album']['name'],
                         'Artist': artist,
                         'ID': key,
                         'Spotify': track['track']['href'],
                         'DurationSpoty': track['track']['duration_ms'] / 1000}
                    )
                else:
                    c.execute('SELECT spotify.title as stitle, ' +
                              'spotify.title as stitle, ' +
                              'spotify.album as salbum, ' +
                              'spotify.artist as sartist, ' +
                              'oldid, url, ' +
                              'tracks.title as ttitle, ' +
                              'tracks.artist as tartist, ' +
                              'tracks.id as id, ' +
                              'spotify.length as slength, ' +
                              'tracks.length as tlength ' +
                              'FROM spotify, tracks WHERE spotify.oldid = ? AND tracks.id = spotify.id', (key, ))
                    row = c.fetchone()
                    tmp = {
                        'TitleSpoty': row['stitle'],
                        'AlbumSpoty': row['salbum'],
                        'ArtistSpoty': row['sartist'],
                        'IDSpoty': row['oldid'],
                        'Title': row['ttitle'],
                        'Album': row['salbum'],
                        'Artist': row['tartist'],
                        'ID': row['id'],
                        'Spotify': row['url'],
                        'DurationSpoty': row['slength'],
                        'Duration': row['tlength']
                    }
                    result.append(tmp)
            result.extend(self.correctMany(tobecorrected))

            offset = offset + json['limit']
            total = json['total']
            if offset > total:
                break

        toBeAdded = self.getMissingData(c, result)
        for item in toBeAdded:
            c.execute("INSERT OR REPLACE INTO tracks (id, title, artist, length, added_time, similar_tracks_added_time, tags_added_time) VALUES (?,?,?,?,?, (SELECT similar_tracks_added_time FROM tracks WHERE id = ? LIMIT 1), (SELECT tags_added_time FROM tracks WHERE id = ? LIMIT 1))",
                      [item['ID'], item['Title'], item['Artist'], item['Duration'], int(time.time()), item['ID'], item['ID']])
            c.execute("INSERT OR REPLACE INTO spotify VALUES (?,?,?,?,?,?,?)",
                      [item['ID'], item['IDSpoty'], item['Spotify'], item['TitleSpoty'], item['AlbumSpoty'], item['ArtistSpoty'], item['DurationSpoty']])

        conn.commit()
        conn.close()
        return result

    ##
    def correctMany(self, tobecorrected):
        result = list()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.WORKER) as executor:
            # Start the load operations and mark each future with its URL
            future_getData = {executor.submit(
                self.getCorrectInfo, t): t for t in tobecorrected}
            for future in concurrent.futures.as_completed(future_getData):
                t = future_getData[future]
                try:
                    track = future.result()
                except Exception as exc:
                    print(str(t) + 'generated an exception: ' + str(exc))
                else:
                    if track is not None:
                        result.append(track)
                        print('Done: ' + t['Title'] + '-' + t['Artist'] +
                              ' --> ' + track['Title'] + '-' + track['Artist'])
                    else:
                        print('Done (not found): ' + str(t))
        return result

    def getLastFMTop(self, user):
        url = "http://ws.audioscrobbler.com/2.0/?method=user.getTopTracks&user=" + \
            quote(user, safe='') + "&period=overall&limit=50&api_key=" + \
            self.lastfm_secret + "&format=json"
        d = requests.get(url).json()
        self.lastfmapicalls += 1
        if 'toptracks' in d:
            d = d['toptracks']['track']
            fulltrackinfos = list()
            for track in d:
                if 'artist' in track:
                    fulltrackinfos.append({
                                          'Title': track['name'],
                                          'Artist': track['artist']['name'],
                                          'ID': self.createID(track['artist']['name'], track['name'])
                                          })
            return self.correctMany(fulltrackinfos)

        return None

    def getCorrectInfo(self, info, alreadytried=False):
        try:
            url = "http://ws.audioscrobbler.com/2.0/?method=track.getInfo&artist=" + \
                quote(info['Artist'], safe='') + "&track=" + quote(info['Title'], safe='') + \
                "&autocorrect=1&api_key=" + self.lastfm_secret + "&format=json"
            #print("correct: " + url)
            d = requests.get(url).json()
            self.lastfmapicalls += 1

            if not alreadytried and (('track' in d and 'playcount' in d['track'] and int(d['track']['playcount']) < 150) or ('error' in d)):
                # correct artist
                url = "http://ws.audioscrobbler.com/2.0/?method=artist.getCorrection&artist=" + \
                    quote(info['Artist'], safe='') + "&api_key=" + \
                    self.lastfm_secret + "&format=json"
                x = requests.get(url).json()
                self.lastfmapicalls += 1
                if 'corrections' in x and 'correction' in x['corrections'] \
                    and 'artist' in x['corrections']['correction'] \
                        and 'name' in x['corrections']['correction']['artist']:
                    info['Artist'] = x['corrections']['correction']['artist']['name']

                # correct title
                url = "http://ws.audioscrobbler.com/2.0/?method=track.getCorrection&artist=" + \
                    quote(info['Artist'], safe='') + "&track=" + quote(info['Title'],
                                                                       safe='') + "&api_key=" + self.lastfm_secret + "&format=json"
                x = requests.get(url).json()
                self.lastfmapicalls += 1
                if 'corrections' in x and 'correction' in x['corrections'] \
                    and 'track' in x['corrections']['correction'] \
                        and 'name' in x['corrections']['correction']['track']:
                    info['Title'] = x['corrections']['correction']['track']['name']

                # 2nd try:
                return self.getCorrectInfo(info, True)

            if 'track' in d:
                d = d['track']

                if 'artist' in d and 'name' in d and 'name' in d['artist']:
                    info['Artist'] = d['artist']['name']
                    info['Title'] = d['name']
                    info['ID'] = self.createID(info['Artist'], info['Title'])
                    info['type'] = 'track'
                    if 'mbid' in d['artist']:
                        info['AristMBID'] = d['artist']['mbid']
                    if 'album' in d:
                        if 'title' in d['album']:
                            info['Album'] = d['album']['title']
                        if 'mbid' in d['album']:
                            info['AlbumMBID'] = d['album']['mbid']
                    if 'mbid' in d:
                        info['TitleMBID'] = d['mbid']
                    if 'duration' in d:
                        info['Duration'] = int(d['duration']) / 1000
                    if 'toptags' in d and 'tag' in d['toptags']:
                        info['Tags'] = d['toptags']['tag']
                    return info
        except:
            print("An exception occured while trying to correct " + str(info))
        print('Not successfull: ' + url)
        return None

    ###

    def getSimilarTracks(self, origTrack):
        db = self.getDBCursor()
        conn = db['conn']
        c = db['cursor']

        collectedInfo = list()
        artist = origTrack['Artist']
        title = origTrack['Title']

        c.execute('SELECT count(id) FROM tracks WHERE id = ? AND similar_tracks_added_time > ?', [
                  origTrack['ID'], int(time.time() - 700000)])
        row = c.fetchone()
        if row[0] > 0:
            c.execute('SELECT DISTINCT * FROM tracks, similartracks WHERE (id2 = ? AND id1 = id) OR (id1 = ? AND id2 = id)',
                      [origTrack['ID'], origTrack['ID']])
            rows = c.fetchall()
            for row in rows:
                track = {'Title':  row['title'],
                         'Artist': row['artist'],
                         'ID': row['id'],
                         'Match': row['similarity'],
                         'type': 'track'}
                collectedInfo.append(track)

        else:
            url = "http://ws.audioscrobbler.com/2.0/?method=track.getsimilar&artist=" + \
                quote(artist, safe='') + "&track=" + quote(title,
                                                           safe='') + "&api_key=" + self.lastfm_secret + "&format=json"
            #print("Similar: " + url)
            response = requests.get(url).json()
            self.lastfmapicalls += 1
            foundRelated = False
            if not response.get('similartracks') is None:
                for d in response['similartracks']['track']:
                    if 'match' in d and 'name' in d and 'artist' in d and 'name' in d['artist']:
                        track = {'Title':  d['name'],
                                 'Artist': d['artist']['name'],
                                 'ID': self.createID(d['artist']['name'], d['name']),
                                 'Match': d['match']}
                        if 'mbid' in d['artist']:
                            track['AristMBID'] = d['artist']['mbid']
                        if 'mbid' in d:
                            track['TitleMBID'] = d['mbid']

                        c.execute("INSERT OR REPLACE INTO similartracks VALUES (?,?,?)",
                                  [origTrack['ID'], track['ID'], track['Match']])
                        c.execute("INSERT OR REPLACE INTO tracks (id, title, artist, added_time, similar_tracks_added_time, tags_added_time) VALUES (?,?,?,?, (SELECT similar_tracks_added_time FROM tracks WHERE id = ? LIMIT 1), (SELECT tags_added_time FROM tracks WHERE id = ? LIMIT 1))",
                                  [origTrack['ID'], origTrack['Title'], origTrack['Artist'], int(time.time()), origTrack['ID'], origTrack['ID']])

                        collectedInfo.append(track)
                        foundRelated = True
                    else:
                        print('Similar Tracks: skipped one response for: ' +
                              title + ' - ' + artist)
            else:
                print('No similar tracks found for: ' + title + ' - ' + artist)

            if foundRelated:
                c.execute("INSERT OR REPLACE INTO tracks (id, title, artist, similar_tracks_added_time, added_time, tags_added_time) VALUES (?,?,?,?, ?, (SELECT tags_added_time FROM tracks WHERE id = ? LIMIT 1))",
                          [origTrack['ID'], origTrack['Title'], origTrack['Artist'], int(time.time()), int(time.time()), origTrack['ID']])
                conn.commit()  # skip updates if not found

        conn.close()
        return collectedInfo

    ###
    def getTags(self, track):
        collectedInfo = dict()

        db = self.getDBCursor()
        conn = db['conn']
        c = db['cursor']

        c.execute('SELECT count(id) FROM tracks WHERE id = ? AND tags_added_time > ?', [
                  track['ID'], int(time.time() - 700000)])
        row = c.fetchone()
        if row[0] > 0:
            c.execute('SELECT DISTINCT * FROM tags WHERE id = ?',
                      [track['ID']])
            rows = c.fetchall()
            for row in rows:
                collectedInfo[row['tag']] = row['count']
        else:
            url = "http://ws.audioscrobbler.com/2.0/?method=track.getTopTags&artist=" + quote(track['Artist'], safe='') + \
                "&track=" + quote(track['Title'], safe='') + \
                "&autocorrect=1&api_key=" + self.lastfm_secret + "&format=json"
            #print("Tags: " + url)
            response = requests.get(url).json()
            self.lastfmapicalls += 1
            if 'toptags' in response:
                for d in response['toptags']['tag']:
                    # 5-prozent-huerde ;)
                    if 'name' in d and 'count' in d and d['count'] >= 5:
                        collectedInfo[d['name']] = d['count']
                        c.execute("INSERT OR REPLACE INTO tags VALUES (?,?,?)",
                                  [track['ID'], d['name'], d['count']])
                c.execute("INSERT OR REPLACE INTO tracks (id, title, artist, tags_added_time, added_time, similar_tracks_added_time) VALUES (?,?,?,?, ?, (SELECT similar_tracks_added_time FROM tracks WHERE id = ? LIMIT 1))",
                          [track['ID'], track['Title'], track['Artist'], int(time.time()), int(time.time()), track['ID']])
                conn.commit()  # skip updates if not found

        conn.close()
        return collectedInfo

    def addRelatedTracks(self, G, tracks):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.WORKER) as executor:
            # Start the load operations and mark each future with its URL
            future_getData = {executor.submit(
                self.getSimilarTracks, t): t for t in tracks}
            for future in concurrent.futures.as_completed(future_getData):
                t = future_getData[future]
                try:
                    if not 'ID' in t:
                        t['ID'] = self.createID(t['Artist'], t['Title'])

                    if not t['ID'] in G:
                        print(
                            'strange. this song should really be in the graph... adding ... ' + str(t))
                        G.add_node(t['ID'], attr_dict=t)
                    jsondata = future.result()
                except Exception as exc:
                    print(str(t) + 'generated an exception (related): ' + str(exc))
                else:
                    if jsondata is not None:
                        for track in jsondata:
                            if track['ID'] not in G:
                                track['relatedfound'] = False
                                track['type'] = 'track'
                                G.add_node(track['ID'], attr_dict=track)
                            G.add_weighted_edges_from([
                                                      (t['ID'], track['ID'],
                                                       1 / track['Match'])
                                                      ])
                        nx.set_node_attributes(
                            G, 'relatedfound', {t['ID']: True})

    def addRelatedTags(self, G, tracks):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.WORKER) as executor:
            # Start the load operations and mark each future with its URL
            future_getData = {executor.submit(
                self.getTags, t): t for t in tracks}
            for future in concurrent.futures.as_completed(future_getData):
                t = future_getData[future]
                try:
                    if not 'ID' in t:
                        t['ID'] = self.createID(t['Artist'], t['Title'])

                    if not t['ID'] in G:
                        print(
                            'strange. this song should really be in the graph... adding ... ' + str(t))
                        G.add_node(t['ID'], attr_dict=t)
                    data = future.result()
                except Exception as exc:
                    print(str(t) + 'generated an exception (tagging): ' + str(exc))
                else:
                    if data is not None:
                        for tag, count in data.items():
                            tagid = '__' + tag.lower() + '__'
                            if tagid not in G:
                                G.add_node(tagid, attr_dict={'type': 'tag'})
                            G.add_weighted_edges_from([
                                                      (t['ID'], tagid,
                                                       100000 / count)
                                                      ])
                        nx.set_node_attributes(G, 'tagset', {t['ID']: True})

    def addEdgesWithinArtists(self, G, weight):
        nodes = G.nodes(data=True)
        for n in nodes:
            if (not 'type' in n[1] or (n[1]["type"] != "tag" and n[1]["type"] != "artist")) and 'Artist' in n[1]:
                artist = n[1]["Artist"]
                artistID = re.sub(r'\W+', '', artist.lower())
                artistID = '___ART_' + artistID + '__'
                if artistID not in G:
                    G.add_node(artistID, attr_dict={'type': 'artist',
                                                    'Artist': artist})
                G.add_weighted_edges_from([(n[1]['ID'], artistID, weight)])

    def waitForLastFm(self):
        diff = time.time() - self.lasttimestamp
        print(str(self.lastfmapicalls) + " calls in " + str(diff) + "sec.")
        if diff > 0 and self.lastfmapicalls / diff > 5:
            wait = 1 + self.lastfmapicalls / 5 - diff
            print("waiting " + str(wait) + "sec. for LastFM API")
            time.sleep(wait)
            self.lastfmapicalls = 0
            self.lasttimestamp = time.time()

    def createDatabase(self):
        db = self.getDBCursor()
        conn = db['conn']
        c = db['cursor']

        # Create table
        c.execute('''CREATE TABLE IF NOT EXISTS tracks (id TEXT PRIMARY KEY, title TEXT, artist TEXT, length INTEGER, added_time INTEGER, similar_tracks_added_time INTEGER, tags_added_time INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS spotify (id TEXT PRIMARY KEY, oldid TEXT, url TEXT, title TEXT, album TEXT, artist TEXT, length INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS youtube (id TEXT PRIMARY KEY, url TEXT, title TEXT, description TEXT, youtube_id TEXT, length INTEGER)''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS tags (id TEXT, tag TEXT, count INTEGER, PRIMARY KEY (id, tag))''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS similartracks (id1 TEXT, id2 TEXT, similarity REAL, PRIMARY KEY (id1, id2))''')

        #c.execute('''CREATE TABLE IF NOT EXISTS plays (titleid TEXT, timestamp TEXT, PRIMARY KEY (titleid, timestamp))''')
        #c.execute('''CREATE TABLE IF NOT EXISTS type (title TEXT, type INTEGER, PRIMARY KEY (title))''')
        #c.execute('''CREATE TABLE IF NOT EXISTS bpm (titleid TEXT, bpm INTEGER, PRIMARY KEY (titleid))''')

        # save changes
        conn.commit()
        conn.close()

    def getMissingData(self, c, data):
        dataIDs = [f['ID'] for f in data]
        placeholder = '?'  # For SQLite. See DBAPI paramstyle.
        placeholders = ', '.join([placeholder] * len(dataIDs))
        query = 'SELECT id FROM tracks WHERE id IN (%s)' % placeholders
        c.execute(query, dataIDs)
        rows = c.fetchall()
        dbIDs = [r['id'] for r in rows]
        toAdd = list()
        for i in data:
            if not i['ID'] in dbIDs:
                toAdd.append(i)
        return toAdd

    def getDBCursor(self):
        conn = sqlite3.connect('data/playlister_cache.db', timeout=300.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        return {'conn': conn, 'cursor': c}

    def updateTracksInDB(self, tracks):
        db = self.getDBCursor()
        conn = db['conn']
        c = db['cursor']
        toAdd = self.getMissingData(c, tracks)
        for i in toAdd:
            c.execute("INSERT OR REPLACE INTO tracks VALUES (?,?,?,?,?,(SELECT similar_tracks_added_time FROM tracks WHERE id = ? LIMIT 1), (SELECT tags_added_time FROM tracks WHERE id = ? LIMIT 1))",
                      [i['ID'], i['Title'], i['Artist'], i['Duration'], int(time.time()), i['ID'], i['ID']])
            # if 'Tags' in i:
            #    for tag in i['Tags']:
            #        c.execute("INSERT OR REPLACE INTO tags VALUES (?,?,?)",
            #                  [i['ID'], tag['name'], i['Title']])
            # if 'Spotify' in i:
            #    c.execute("INSERT OR IGNORE INTO spotify VALUES (?,?,?,?,0,?)",
            #              [i['ID'], i['Spotify'], i['Duration'], int(time.time()), int(time.time())])
        # Save (commit) the changes
        conn.commit()

        return toAdd

    # TODO: should be a static funtcion
    def csv_to_playlist(self, csv_path):
        playlist = []
        with open(csv_path, mode='r') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';',
                                    quoting=csv.QUOTE_NONE)
            for row in reader:
                playlist.append({
                    'Artist': row['Artist'],
                    'Title': row['Title'],
                    'ID': self.createID(row['Artist'], row['Title']),
                    'Duration': None
                })

        return playlist

    ### START ###

    # spotify
    spoti_user = None
    spoti_user_token = None

    # last.fm
    lastfm_secret = None

    WORKER = 100

    lastfmapicalls = 0
    lasttimestamp = 0

    # TODO: most of this does not belong into the __init__ function but rather in the main call...
    def __init__(self):
        secrets = {}
        with open("data/my_secrets.json", 'r') as file_:
            secrets = json.load(file_)
            self.spoti_user = secrets['spoti_user']
            self.lastfm_secret = secrets['lastfm_secret']

        with open("exceptions.txt", "a", encoding="utf8") as exfile:
            exfile.write("----------------- NEW ------------------\n")

        # init DB
        self.createDatabase()

        # init spotify
        response = requests.post("https://accounts.spotify.com/api/token",
                                 data={'grant_type': 'client_credentials'},
                                 auth=(secrets['spoti_client_id'],
                                       secrets['spoti_client_secret'])
                                 )
        response = response.json()
        if 'access_token' in response:
            self.spoti_user_token = response['access_token']

        self.lastfmapicalls = 0
        self.lasttimestamp = time.time()

        # define tracks
        # from spotify. e.g. {'63YEZPSApGhzI112HmY9iR', '66ruNx1uLlq3qN5s7M19EP', '7rgNwnjHN97i4s6rb5hVzY', '5y7cOeq1lSSb68ztF4YpXx'}
        playlists = None
        additionalTracks = self.csv_to_playlist(
            'example_playlists/33_party.csv')

        mustHave = []
        mustHave.extend(additionalTracks)
        if (playlists != None):
            for playlist in playlists:
                mustHave.extend(self.getSpotifyTracks(playlist))
                #mustHave = self.getSpotifyTracks(self.spoti_playlistmust) #self.spoti_playlisttest) #

        with open('data/musthave.json', 'w') as outfile:
            json.dump(mustHave, outfile)

        # update all must-have tracks and safe them to db
        self.updateTracksInDB(mustHave)

        pool = list()
        pool.extend(mustHave)

        G = nx.Graph()
        for t in pool:
            t['relatedfound'] = False
            G.add_node(t['ID'], attr_dict=t)

        self.waitForLastFm()
        self.addRelatedTracks(G, mustHave)

        oldPathWeights = sys.maxsize
        newPathWeights = sys.maxsize - 1
        while oldPathWeights > newPathWeights:
            # extract subgraphs
            graphlist = list()
            sub_graphs = nx.connected_component_subgraphs(G)
            for sg in sub_graphs:
                graphlist.append({
                                 'nodes': sg.number_of_nodes(),
                                 'graph': sg
                                 })
            graphlist = sorted(
                graphlist, key=lambda k: k['nodes'], reverse=True)
            newpoolbig = list()
            newpoolsmall = list()
            for graphnum, graph in enumerate(graphlist):
                notvisited = nx.get_node_attributes(
                    graph['graph'], "relatedfound")
                titles = nx.get_node_attributes(graph['graph'], "Title")
                artists = nx.get_node_attributes(graph['graph'], "Artist")
                for k, v in notvisited.items():
                    if not v:
                        if graphnum > 1:
                            newpoolsmall.append(
                                {'Title': titles[k], 'Artist': artists[k], 'ID': k})
                        newpoolbig.append(
                            {'Title': titles[k], 'Artist': artists[k], 'ID': k})

            self.waitForLastFm()
            newpool = list()
            if len(newpoolsmall) < 250:
                shuffle(newpoolbig)
                newpool = newpoolbig[:250]
            else:
                shuffle(newpoolsmall)
                newpool = newpoolsmall[:250]

            self.addRelatedTracks(G, newpool)
            self.waitForLastFm()
            self.addRelatedTags(G, newpool)
            self.addEdgesWithinArtists(G, 500000)  # last variable is weight

            print(str(nx.info(G)))

            H = G.copy()
            top = mustHave
            shuffle(top)
            titles = nx.get_node_attributes(H, "Title")
            artists = nx.get_node_attributes(H, "Artist")
            edges = H.edges()
            for edge in edges:
                if str(edge[0]).startswith("__") and str(edge[1]).startswith("__"):  # jumping over tags
                    nx.set_edge_attributes(H, 'weight', {edge: (
                        H[edge[0]][edge[1]]['weight'] + 200000)})
                # small penalty for using one tag
                elif (str(edge[0]).startswith("__") or str(edge[1]).startswith("__")):
                    nx.set_edge_attributes(H, 'weight', {edge: (
                        H[edge[0]][edge[1]]['weight'] + 5000)})  # small penalty
                else:
                    if artists[edge[0]] == artists[edge[1]]:  # following same artist
                        nx.set_edge_attributes(H, 'weight', {edge: (
                            H[edge[0]][edge[1]]['weight'] + 500000)})
                    # following same title (maybe different artist?
                    if titles[edge[0]] == titles[edge[1]]:
                        nx.set_edge_attributes(H, 'weight', {edge: (
                            H[edge[0]][edge[1]]['weight'] + 100000)})

            titlelist = list()
            weightSum = 0
            try:
                start_node = top[0]
                while len(top) > 1:
                    bestIdx = -1
                    betsLength = -1
                    for topidx in range(len(top)-1):
                        if start_node != top[topidx + 1]:
                            try:
                                plength = nx.shortest_path_length(
                                    H, source=start_node['ID'], target=top[topidx + 1]['ID'], weight='weight')
                                if plength > 0 and (plength < betsLength or betsLength < 0):
                                    betsLength = plength
                                    bestIdx = topidx + 1
                            except nx.NetworkXNoPath as ex:
                                print('no connection between %s and %s' % (
                                    str(start_node['ID']), str(top[topidx + 1]['ID'])))
                    if (betsLength < 0):
                        weightSum += 10000000
                        titlelist.append(top[0])
                        del top[0]
                        start_node = top[0]
                    else:
                        path = nx.shortest_path(
                            H, source=start_node['ID'], target=top[bestIdx]['ID'], weight='weight')
                        start_node = top[bestIdx]
                        weightSum += betsLength
                        for i in range(len(path)-1):
                            if not str(path[i]).startswith('__'):
                                titlelist.append(H.node[path[i]])
                                # remove already visited tracks
                                H.remove_node(path[i])
                            top = [d for d in top if d.get('ID') != path[i]]
                            #nx.set_edge_attributes(H, 'weight', {(path[i], path[i + 1]):(H[path[i]][path[i + 1]]['weight'] + 10000000)})
                titlelist.append(top[0])  # add the last one

                # add missing information to playlist
                newlist = []
                for t in titlelist:
                    if (not t):
                        print(
                            "WARNING: An empty or None item made its way into the playlist. There may be an issue. Skipping.")
                        continue
                    if (not 'Duration' in t) or (t['Duration'] is None) or (t['Duration'] <= 0):
                        new_t = self.getCorrectInfo(t)
                        if (not new_t is None and len(new_t) > 0):
                            t = new_t
                    newlist.append(t)
                titlelist = newlist

                with open('data/songs.json', 'w') as outfile:
                    json.dump(titlelist, outfile)

                importantlist = list()
                for track in titlelist:
                    if track is None:
                        print("Playlist contains a 'None' item!! Skipping.")
                        continue
                    for track2 in mustHave:
                        if track['ID'] == track2['ID']:
                            importantlist.append(track)
                            break
                with open('data/important.json', 'w') as outfile:
                    json.dump(importantlist, outfile)

                oldPathWeights = newPathWeights
                newPathWeights = weightSum
            except Exception as ex:
                print("could not get tracklist " + str(ex))
                with open("exceptions.txt", "a", encoding="utf8") as exfile:
                    exfile.write('Exception:\n%s \n' % str(ex))


if __name__ == "__main__":
    GraphCreator()
