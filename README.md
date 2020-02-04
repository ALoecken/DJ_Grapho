# DJ Grapho
This set of files creates a playlist that transits nicely over similar tracks. The goal is to gather music from different genres and let them play on a party without the "DJ Shuffle" effect. 
It uses the Last.FM database to receive metadata, the Spotify API to get a playlist as input, and the Youtube API to upload the playlist to an account. 

## How to run
This is a work in progress and requires much manual work!!
It also requires python 3+ and several libraries.

### Create a playlist in CSV format or at Spotify

### Set you credentials in data\credentials.json 
You need to set up your own developer projects for the different APIs.
- Spotify credentials need to be set up here: https://developer.spotify.com/dashboard/ and can be added to data/my_secrets.json
- Last.FM credentials here: https://www.last.fm/api/account/create and can be added to data/my_secrets.json
- Youtube credentials need to be downloaded to data/client_secret.json from here: https://console.developers.google.com/apis/api/youtube.googleapis.com/overview?project={{yourproject}}

### Change the code in src\main_withdb.py to load your playlist (instead of mine): lines 506-507

### Start 'python src\main_withdb.py' (fills the database and creates the list at )
- This will read the songs in your playlist and get their metadata. 
- It will create a graph based on similarities and try to connect all songs
- If it did not find all connections, it will repeat the process and include the most similar songs to the graph
- It will create two json playlist: songs.json (includingyour tracks and the related once) + important.json (includes only the given tracks in new order)
- The program may run forever and increases the size of the database over time to find better connections

### Run 'python src\echo_playlist.py' to echo the generated playlist or 'python src\experimental\create_youtubelist.py' to create a youtube playlist.


## Experimental
- If you have a folder full of mp3s in the name format Artist-Title.mp3, you may use 'create_m3u.py' to create a playlist for files on your pc
- create_youtubelist.py creates a youtubelist ;) but needs you to set up a youtube-project first (to get the API credentials)

## Requirements
TBD

## Next TODOS:
- Use arguments instead of having to change code.
- Not only rely on LastFM, also use Spotify, bpmdatabase, and Youtube Metadata to check for similar videos.
