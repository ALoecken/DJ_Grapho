#!/usr/bin/python
#encoding: utf-8
from apiclient.discovery import build
from apiclient.errors import HttpError
from bs4 import BeautifulSoup
from collections import defaultdict
import concurrent.futures
from datetime import datetime
import matplotlib.pyplot as plt
import networkx as nx
from oauth2client.tools import argparser
from random import shuffle
import requests
import sqlite3
import urllib
from urllib.parse import quote
from threading import Thread
   

class Reader:
    # spotify
    client_id = "client_id"
    client_secret = "client_secret"
    spoti_user = "user_id" # andreas
    spoti_playlistchart97 = "playlist_id" # charts
    spoti_playlistmust = "playlist_id"
    spoti_user_token = "token"

    ## last.fm
    user = "username"
    secret = "your_secret"
    
    WORKER = 100
    # Set DEVELOPER_KEY to the API key value from the APIs & auth > Registered apps
    # tab of
    #   https://cloud.google.com/console
    # Please ensure that you have enabled the YouTube Data API for your project.
    DEVELOPER_KEY = "youtube_key"
    YOUTUBE_API_SERVICE_NAME = "youtube"
    YOUTUBE_API_VERSION = "v3"

    def getSpotifyTracks(self, playlistid):
        offset = 0
        while True:
            response = requests.get('https://api.spotify.com/v1/users/' + self.spoti_user + '/playlists/' + playlistid + "/tracks?limit=100&offset=" + str(offset), 
                                    headers={'Authorization': 'Bearer ' + self.spoti_user_token, "Accept": "application/json"})
            json = response.json()
            tracks = json['items']

            result = list()
            for track in tracks:
                # todo: also add other artists?
                result.append({'Title':track['track']['name'], 'Album':track['track']['album']['name'], 'Artist': track['track']['artists'][0]['name']})
                
            offset = offset + json['limit']
            total =  json['total']
            if offset > total:
                break
        return result

    def getRecentTracks(self, page, since=0):
        collectedInfo = []
        url = "http://ws.audioscrobbler.com/2.0/?method=user.getRecentTracks&user=" + self.user + "&api_key=" + self.secret + "&from=" + str(since) + "&limit=200&format=json&page=" + str(page)
        response = requests.get(url).json()
        for d in response['recenttracks']['track']:
            if 'date' in d:
                artid = d['artist']['mbid']
                if len(artid) < 1:
                    artid = 'n' + str(hash(d['artist']['#text']))
                albid = d['album']['mbid']
                if len(albid) < 1:
                    albid = 'n' + str(hash(d['artist']['#text'] + d['album']['#text']))
                titid = d['mbid']
                if len(titid) < 1:
                    titid = 'n' + str(hash(d['artist']['#text'] + d['name']))
                collectedInfo.append({'Artist':d['artist']['#text'], 'Album':d['album']['#text'], 'Title':d['name'], 'Time':datetime.fromtimestamp(int(d['date']['uts'])), 'AristMBID':artid, 'AlbumMBID':albid, 'TitleMBID':titid})
        return {'info':collectedInfo, 'pages':int(response['recenttracks']['@attr']['totalPages'])}
    
    ###
    def getSimilarTracks(self, mbid, title, artist):
        collectedInfo = []
        url = "http://ws.audioscrobbler.com/2.0/?method=track.getsimilar&mbid=" + mbid + "&api_key=" + self.secret + "&format=json"
        if mbid.startswith('n'):
            url = "http://ws.audioscrobbler.com/2.0/?method=track.getsimilar&artist=" + quote(artist, safe='') + "&track=" + quote(title, safe='')  + "&api_key=" + self.secret + "&format=json"
            #print("Can't search for ID: " + mbid)
            #return None
        response = requests.get(url).json()
        for d in response['similartracks']['track']:
            if 'name' in d:
                artid = 'n' + str(hash(d['artist']['name']))
                if 'mbid' in d['artist']:
                    if len(d['artist']['mbid']) > 1:
                        artid = d['artist']['mbid']
                titid = 'n' + str(hash(d['artist']['name'] + d['name']))
                if 'mbid' in d:
                    if len(d['mbid']) > 1:
                        titid = d['mbid'] 
                collectedInfo.append({'Artist':d['artist']['name'], 'Title':d['name'], 'AristMBID':artid, 'TitleMBID':titid, 'Match':d['match']})
        return {'info':collectedInfo}
    ###
    
    def getTags(self, mbid, title, artist, kind):
        collectedInfo = []
        url = ""
        if kind == "title":
            url = "http://ws.audioscrobbler.com/2.0/?method=track.getTopTags&artist=" + quote(artist, safe='') + "&track=" + quote(title, safe='')  + "&autocorrect=1&api_key=" + self.secret + "&format=json"
        elif kind == "artist":
            url = "http://ws.audioscrobbler.com/2.0/?method=artist.getTopTags&artist=" + quote(artist, safe='') + "&autocorrect=1&api_key=" + self.secret + "&format=json"
        elif kind == "album":
            url = "http://ws.audioscrobbler.com/2.0/?method=album.getTopTags&artist=" + quote(artist, safe='') + "&album=" + quote(title, safe='')  + "&autocorrect=1&api_key=" + self.secret + "&format=json"
            
        response = requests.get(url).json()
        if 'toptags' in response:
            for d in response['toptags']['tag']:
                if 'name' in d:
                    collectedInfo.append({'Name':d['name'], 'Count':d['count']})
        return {'info':collectedInfo}
    
    def getCorrectInfo(self, info):
        url = "http://ws.audioscrobbler.com/2.0/?method=track.getInfo&artist=" + \
            quote(info['Artist'], safe='') + "&track=" + quote(info['Title'], safe='') + \
            "&autocorrect=1&api_key=" + self.secret + "&format=json"
        d = requests.get(url).json()
        if 'name' in d['track']:
            d = d['track']
            if 'artist' in d and 'album' in d and 'mbid' in d:
                artid = d['artist']['mbid']
                if len(artid) < 1:
                    artid = 'n' + str(hash(d['artist']['#text']))
                albid = d['album']['mbid']
                if len(albid) < 1:
                    albid = 'n' + str(hash(d['artist']['#text'] + d['album']['#text']))
                titid = d['mbid']
                if len(titid) < 1:
                    titid = 'n' + str(hash(d['artist']['#text'] + d['name']))
                return {
                    'Artist':d['artist']['name'], 
                    'Title':d['name'], 
                    'Album':d['album']['title'],
                    'AristMBID':artid, 
                    'TitleMBID':titid,
                    'AlbumMBID':albid
                    }
        return None
        
    def getYoutubeLink(self, query):
        youtube = build(self.YOUTUBE_API_SERVICE_NAME, self.YOUTUBE_API_VERSION, developerKey=self.DEVELOPER_KEY)

        # Call the search.list method to retrieve results matching the specified
        # query term.
        search_response = youtube.search().list(
                                                q=query,
                                                part="id,snippet",
                                                maxResults=10
                                                ).execute()

        videos = []

        # Add each result to the appropriate list, and then display the lists of
        # matching videos, channels, and playlists.
        for search_result in search_response.get("items", []):
            if search_result["id"]["kind"] == "youtube#video":
                videos.append("%s (https://www.youtube.com/watch?v=%s)" % (search_result["snippet"]["title"],
                              search_result["id"]["videoId"]))

        print ("Videos:\n", "\n".join(videos), "\n")

    def createDatabase(self, dbConn):
        # create cursor
        c = dbConn.cursor()

        # Create table
        c.execute('''CREATE TABLE IF NOT EXISTS container (artistid TEXT, albumid TEXT, titleid TEXT, PRIMARY KEY (artistid, titleid))''')
        c.execute('''CREATE TABLE IF NOT EXISTS tracks (titleid TEXT PRIMARY KEY, title TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS artists (artistid TEXT PRIMARY KEY, artist text)''')
        c.execute('''CREATE TABLE IF NOT EXISTS albums (artistid TEXT, albumid TEXT PRIMARY KEY, album TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS plays (titleid TEXT, timestamp TEXT, PRIMARY KEY (titleid, timestamp))''')
        c.execute('''CREATE TABLE IF NOT EXISTS similartracks (title1 TEXT, title2 TEXT, similarity REAL, PRIMARY KEY (title1, title2))''')
        c.execute('''CREATE TABLE IF NOT EXISTS tags (title TEXT, tag TEXT, count INTEGER, PRIMARY KEY (title, tag))''')
        c.execute('''CREATE TABLE IF NOT EXISTS type (title TEXT, type INTEGER, PRIMARY KEY (title))''')
        c.execute('''CREATE TABLE IF NOT EXISTS bpm (titleid TEXT, bpm INTEGER, PRIMARY KEY (titleid))''')
        
        # save changes
        dbConn.commit()
        return c

    def getNewestDateInDB (self, dbCursor):
        # get newest update
        dbCursor.execute("SELECT timestamp FROM plays ORDER BY timestamp DESC LIMIT 1")
        results = dbCursor.fetchone()
        if results is not None:
            return (int) (datetime.strptime(results[0], "%Y-%m-%dT%H:%M:%S").timestamp())
        else: 
            return 0
    
    def getAllListenedTracks(self, starttime):
        page = 1
        data = self.getRecentTracks(page, starttime)
        pages = data['pages']
        collectedInfo = data['info']
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.WORKER) as executor:
            # Start the load operations and mark each future with its URL
            future_getData = {executor.submit(self.getRecentTracks, page, starttime): page for page in range(2, pages + 1)}
            for future in concurrent.futures.as_completed(future_getData):
                page = future_getData[future]
                try:
                    colInfo = future.result()
                except Exception as exc:
                    print('%r generated an exception: %s' % (page, exc))
                else:
                    collectedInfo.extend(colInfo['info'])
                    print('%i / %i done ' % (page, pages))
        return collectedInfo
    
    def saveTracksToDB(self, tracks, c, conn, type=0):
    #clean mbids and save to DB:
        for info in tracks:
            ## takes too long!
            #            if info['AristMBID'].startswith('n') or info['AlbumMBID'].startswith('n') or info['TitleMBID'].startswith('n'):
            #                print (info)
            #                trackInfo = self.getCorrectInfo(info)
            #                print (trackInfo)
            #                if trackInfo is not None:
            #                    info['AristMBID'] = trackInfo['AristMBID']
            #                    info['AlbumMBID'] = trackInfo['AlbumMBID']
            #                    info['TitleMBID'] = trackInfo['TitleMBID']
            c.execute("INSERT OR REPLACE INTO tracks VALUES (?,?)", 
                      [info["TitleMBID"], info["Title"]])
            c.execute("INSERT OR REPLACE INTO artists VALUES (?,?)",
                      [info["AristMBID"], info["Artist"]])
            c.execute("INSERT OR REPLACE INTO albums VALUES (?,?,?)",
                      [info["AristMBID"], info["AlbumMBID"], info["Album"]])
            c.execute("INSERT OR REPLACE INTO container VALUES (?,?,?)", 
                      [info["AristMBID"], info["AlbumMBID"], info["TitleMBID"]])
            if "Time" in info:
                c.execute("INSERT OR REPLACE INTO plays VALUES (?,?)",
                          [info["TitleMBID"], info["Time"].isoformat()])
            c.execute("INSERT OR REPLACE INTO type VALUES (?,?)",
                      [info["TitleMBID"], type]) # 1=listened!
        
        # Save (commit) the changes
        conn.commit()
    
    def saveRelatedTracks(self, tracks, c, conn):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.WORKER) as executor:
            # Start the load operations and mark each future with its URL
            future_getData = {executor.submit(self.getSimilarTracks, t['TitleMBID'], t['Title'], t['Artist']): t for t in tracks}
            for future in concurrent.futures.as_completed(future_getData):
                t = future_getData[future]
                try:
                    jsondata = future.result()
                except Exception as exc:
                    print('%r generated an exception: %s' % (d, exc))
                else:
                    if jsondata is not None:
                        for track in jsondata['info']: 
                            c.execute("INSERT OR IGNORE INTO container (artistid, titleid) VALUES (?, ?)", 
                                      [track["AristMBID"], track["TitleMBID"]])
                            c.execute("INSERT OR IGNORE INTO tracks VALUES (?, ?)", 
                                      [track["TitleMBID"], track["Title"]])
                            c.execute("INSERT OR IGNORE INTO artists VALUES (?,?)",
                                      [track["AristMBID"], track["Artist"]])
                            c.execute("INSERT OR REPLACE INTO similartracks VALUES (?,?,?)",
                                      [t['TitleMBID'], track["TitleMBID"], track["Match"]])
                            c.execute("INSERT OR IGNORE INTO type VALUES (?,?)",
                                      [track["TitleMBID"], 99]) # 99: related
                    print('%r done ' % (t))
        
        # Save (commit) the changes
        conn.commit()
    
    def spotifyToLastFM(self, tracks):
        converted = list()
        # convert to lastfm
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.WORKER) as executor:
            # Start the load operations and mark each future with its URL
            future_getData = {executor.submit(self.getCorrectInfo, data): data for data in tracks}
            for future in concurrent.futures.as_completed(future_getData):
                data = future_getData[future]
                try:
                    correctedData = future.result()
                except Exception as exc:
                    print('%r generated an exception: %s' % (data, exc))
                else:
                    if correctedData is not None:
                        converted.append(correctedData)
                    print('%r done ' % (data))
        return converted
    
    def saveAlbumTags(self, albums, c, conn):
        failedData = list()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.WORKER) as executor:
            # Start the load operations and mark each future with its URL
            future_getData = {executor.submit(self.getTags, t['AlbumMBID'], t['Album'], t['Artist'], "album"): t for t in albums}
            for future in concurrent.futures.as_completed(future_getData):
                t = future_getData[future]
                try:
                    jsondata = future.result()
                except Exception as exc:
                    print('%r generated an exception: %s' % (t, exc))
                    failedData.append(t)
                else:
                    if jsondata is not None:
                        for tag in jsondata['info']: 
                            c.execute("INSERT OR REPLACE INTO tags VALUES (?,?,?)",
                                      [t['AlbumMBID'], tag["Name"], tag["Count"]])
                    print('%r done ' % (t))

        # Save (commit) the changes
        conn.commit()
        return failedData
        
    def saveTags(self, tracks, c, conn):
        failedData = list()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.WORKER) as executor:
            # Start the load operations and mark each future with its URL
            future_getData = {executor.submit(self.getTags, t['TitleMBID'], t['Title'], t['Artist'], "title"): t for t in tracks}
            for future in concurrent.futures.as_completed(future_getData):
                t = future_getData[future]
                try:
                    jsondata = future.result()
                except Exception as exc:
                    print('%r generated an exception: %s' % (t, exc))
                    failedData.append(t)
                else:
                    if jsondata is not None:
                        for tag in jsondata['info']: 
                            c.execute("INSERT OR REPLACE INTO tags VALUES (?,?,?)",
                                      [t['TitleMBID'], tag["Name"], tag["Count"]])
                    print('%r done ' % (t))

        # Save (commit) the changes
        conn.commit()
        return failedData
    
    def saveArtistTags(self, artists, c, conn):
        failedData = list()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.WORKER) as executor:
            # Start the load operations and mark each future with its URL
            future_getData = {executor.submit(self.getTags, t['ArtistMBID'], None, t['Artist'], "artist"): t for t in artists}
            for future in concurrent.futures.as_completed(future_getData):
                t = future_getData[future]
                try:
                    jsondata = future.result()
                except Exception as exc:
                    print('%r generated an exception: %s' % (t, exc))
                    failedData.append(t)
                else:
                    if jsondata is not None:
                        for tag in jsondata['info']: 
                            c.execute("INSERT OR REPLACE INTO tags VALUES (?,?,?)",
                                      [t['ArtistMBID'], tag["Name"], tag["Count"]])
                    print('%r done ' % (t))

        # Save (commit) the changes
        conn.commit()
        return failedData
    
    def getBPM(self, mbid, artist, title):
        response = requests.get ("https://www.bpmdatabase.com/music/search/?artist=" + quote(artist, safe='') + "&title=" + quote(title, safe=''))
        soup = BeautifulSoup(response.text, "lxml")
        x = soup.find(id="track-table")
        if x is not None:
            tr = x.find("tbody").find("tr")
            art = tr.find("td", attrs={"class": "artist"}).string
            tit = tr.find("td", attrs={"class": "title"}).string
            bpm = tr.find("td", attrs={"class": "bpm"}).string
            data = {
                'orig_artist': artist,
                'orig_title': title,
                'mbid':mbid,
                'artist':art,
                'title':tit,
                'bpm':int(bpm)
                }
            return data
        return None
    
    def getAllTracksWithRelations(self, c):
        c.execute("SELECT DISTINCT tracks.title, artists.artist, container.titleid FROM similartracks, container, tracks, artists " + \
                  " WHERE (similartracks.title1 = container.titleid OR similartracks.title2 = container.titleid) AND " + \
                  "  container.titleid = tracks.titleid AND container.artistid = artists.artistid " + \
                  " ORDER BY tracks.title")
        rows = c.fetchall()
        result = list()
        for row in rows:
            result.append({
                          'Artist':row[1], 
                          'Title':row[0],
                          'TitleMBID':row[2]
                          })
        return result
    
    def getBPMs(self, tracks, c, conn):
        bpms  = list()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.WORKER) as executor:
            # Start the load operations and mark each future with its URL
            future_getData = {executor.submit(self.getBPM, r["TitleMBID"], r["Artist"], r["Title"]): r for r in tracks}
            for future in concurrent.futures.as_completed(future_getData):
                r = future_getData[future]
                try:
                    jsondata = future.result()
                except Exception as exc:
                    print('%r generated an exception: %s' % (r["Title"], exc))
                else:
                    if jsondata is not None:
                        bpms.append(jsondata)
                        if "bpm" in jsondata: 
                            c.execute("INSERT OR REPLACE INTO bpm VALUES (?,?)",
                                      [jsondata['mbid'], jsondata["bpm"]])
                    print('%r done ' % (r["Title"]))
        # Save (commit) the changes
        conn.commit()
        return bpms
    
    # 
    def __init__(self):
        # init spotify
        response = requests.post("https://accounts.spotify.com/api/token", 
                                 data={'grant_type':'client_credentials'}, 
                                 auth=(self.client_id, self.client_secret)
                                 )
        response = response.json()
        if 'access_token' in response:
            self.spoti_user_token = response['access_token']
        
        requests.adapters.DEFAULT_RETRIES = 1
        
        ## create table
        conn = sqlite3.connect('musichistory.db')
        conn.row_factory = sqlite3.Row
        c = self.createDatabase(conn)
        
        starttime = self.getNewestDateInDB(c)

        ## get all data not in db from last.fm:
        alltracks = self.getAllListenedTracks(starttime)
        self.saveTracksToDB(alltracks, c, conn, type=1)
          
        # top tracks:
        toptracks = list() 
        c.execute("SELECT plays.titleid, artists.artist, tracks.title, COUNT(plays.timestamp) as plays, artists.artistid " +
                  "FROM plays,container,tracks,artists " + 
                  "WHERE plays.titleid = tracks.titleid AND container.titleid = tracks.titleid AND container.artistid = artists.artistid " +
                  "GROUP BY plays.titleid ORDER BY plays DESC LIMIT 300")
        rows = c.fetchall()
        for row in rows:
            toptracks.append({
                             'Artist':row[1], 
                             'Title':row[2], 
                             'AristMBID':row[4], 
                             'TitleMBID':row[0]
                             })
                             
        # self.saveRelatedTracks(toptracks, c, conn)
        # self.saveTags(toptracks, c, conn)
        
        ## get spotify lists
        #top97 = self.getSpotifyTracks(self.spoti_playlistchart97)
        #top97 = self.spotifyToLastFM(top97)
        #self.saveTracksToDB(top97, c, conn, 2) # 2 = top
        #self.saveRelatedTracks(top97, c, conn) 
        #self.saveTags(top97, c, conn)
        
        mustHave = self.getSpotifyTracks(self.spoti_playlistmust)
        mustHave = self.spotifyToLastFM(mustHave)
        self.saveTracksToDB(mustHave, c, conn, 3) # 2 = top
        self.saveRelatedTracks(mustHave, c, conn) 
        self.saveTags(mustHave, c, conn)
        
        #get album tags    
        #topalbums = list()
        #c.execute("SELECT DISTINCT * " +
        #          "FROM albums NATURAL JOIN artists ")
        #rows = c.fetchall()
        #for row in rows:
        #    topalbums.append({
        #                  'AlbumMBID':row['albumid'],
        #                  'Album':row['album'],
        #                  'Artist':row['artist']
        #                  })
        #fails = self.saveAlbumTags(topalbums, c, conn)
        #while len(fails) > 0:
        #    print("Next Try!")
        #    fails = self.saveAlbumTags(fails, c, conn)
        #
        ##get artist tags
        #topartists = list()
        #c.execute("SELECT DISTINCT artistid, artist FROM artists ")
        #rows = c.fetchall()
        #for row in rows:
        #    topartists.append({
        #                   'ArtistMBID':row['artistid'],
        #                   'Artist':row['artist']
        #                   })
        #fails = self.saveArtistTags(topartists, c, conn)
        #while len(fails) > 0:
        #    print("Next Try!")
        #    fails = self.saveArtistTags(fails, c, conn)
        
        ## read all 
        #allRelevantTracks = self.getAllTracksWithRelations(c)
        #bpms = self.getBPMs(allRelevantTracks, c, conn)
        

        ## build nodes
        G = nx.Graph()
        # add all tracks
        c.execute("SELECT DISTINCT * FROM container NATURAL JOIN tracks NATURAL JOIN artists ")
        rows = c.fetchall()
        for row in rows:
            G.add_node(str(row['titleid']), 
                       attr_dict={'kind':'song', 'name':row['title'], 'artist':row['artist']})
                
        # add all artists
        c.execute("SELECT DISTINCT * FROM artists ")
        rows = c.fetchall()
        for row in rows:
            G.add_node(str(row['artistid']), 
                       attr_dict={'kind':'artist', 'artist':row['artist']})
                       
        # add all albums
        c.execute("SELECT DISTINCT * FROM albums NATURAL JOIN artists")
        rows = c.fetchall()
        for row in rows:
            G.add_node(str(row['albumid']), 
                       attr_dict={'kind':'album', 'name':row['album'], 'artist':row['artist']})
        
        # add similar tracks
        c.execute("SELECT * FROM similartracks ")
        rows = c.fetchall()
        for row in rows:
            G.add_weighted_edges_from([(str(row['title1']), str(row['title2']), 1 / row['similarity'])])
            
        # add tags to make it easier to connect
        c.execute("SELECT * FROM container ")
        rows = c.fetchall()
        for row in rows:
            G.add_weighted_edges_from([(str(row['titleid']), str(row['albumid']), 1000000)])
            G.add_weighted_edges_from([(str(row['titleid']), str(row['artistid']), 2000000)])
        
        # add tags to make it easier to connect
        c.execute("SELECT * FROM tags ")
        rows = c.fetchall()
        for row in rows:
            G.add_node(str(row['tag']), attr_dict={'kind':'tag'})
            G.add_weighted_edges_from([(str(row['title']), str(row['tag']), 1000000 / row['count'])])
            
        # add bpms to have more connection
        c.execute("SELECT * FROM bpm ")
        rows = c.fetchall()
        for row in rows:
            bpmClass = 'bpm' + str(round(int(row['bpm']) / 5) * 5)
            G.add_node(bpmClass, attr_dict={'kind':'bpm'})
            G.add_weighted_edges_from([(str(row['titleid']), bpmClass, 10000)])

        conn.close()
        
        t = Thread(target = nx.write_yaml, args=(G, "music-old.yaml"))
        t.start()
        print (nx.info(G))

        # extract subgraphs
        graphlist = list()
        sub_graphs = nx.connected_component_subgraphs(G)
        for sg in sub_graphs:
            graphlist.append({
                             'nodes':sg.number_of_nodes(),
                             'graph':sg
                             })
        graphlist = sorted(graphlist, key=lambda k: k['nodes'], reverse=True) 
        
        #        for graph in graphlist:
        #            if graph['nodes'] < 500:
        #                nodes = graph['graph'].nodes(data=True)
        #                for node in nodes:
        #                    if node[1]['kind'] == 'song':
        #                        print(node)
        ## looks good ;)
        #graphlist[0]['graph'] # <-- biggest subgraph

        # takes forever...
        #nodes = nx.center(graphlist[0]['graph'])
        #print(nodes)

        # write graphml
        #nx.write_graphml(G, "./graph.graphml")
        
        #top = toptracks[1:30]
        #top.extend(mustHave)
        top= mustHave
        shuffle(top)
        
        H = graphlist[0]['graph'].copy()
        kinds = nx.get_node_attributes(H, "kind")
        titles = nx.get_node_attributes(H, "name")
        artists = nx.get_node_attributes(H, "artist")
        
        titlelist = list()
        while len(top) > 1:
            path = nx.shortest_path(H, source=top[0]['TitleMBID'], target=top[1]['TitleMBID'], weight='weight')
            for p in path[0:-1]:
                if kinds[p] == "song":
                    titlelist.append({
                                     'mbid':p,
                                     'artist':artists[p],
                                     'title':titles[p]
                                     })
                    top[:] = [d for d in top if d.get('TitleMBID') != p]
                    H.remove_node(p)
        titlelist.append({
                         'mbid':top[0]['TitleMBID'],
                         'artist':artists[top[0]['TitleMBID']],
                         'title':titles[top[0]['TitleMBID']]
                         })
        for title in titlelist:
            print (title['artist'] + " - " + title['title'] )
        #nx.shortest_path(graphlist[0]['graph'], source=top[0]['TitleMBID'], target=top[1]['TitleMBID'],  weight='weight')
        
        t.join() # wait for writing to finish
        print ("done")
        
        ## super! 
        # TODO: doppelte tracks
        # TODO: Artists direkt nacheinander
        

if __name__ == "__main__":Reader() 