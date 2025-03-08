import csv
import subprocess
import os
from flask import Flask, redirect, request, session, jsonify, render_template_string
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import time
from threading import Thread

app = Flask(__name__)
app.secret_key = 's3cr3t_k3y_f0r_s3ss10ns'

# Configuration constants
SPOTIFY_CLIENT_ID = 'ea384b436028496aa42cd04105650a7f'
SPOTIFY_CLIENT_SECRET = '3eef91355b1f498fa605f1b562fe25bb'
REDIRECT_URI = 'http://127.0.0.1:5000/authorize'
SCOPE = 'user-library-read'
CSV_FILE_PATH = 'songs.csv'
SPOTIFY_URLS_FILE = 'spotify_urls.txt'

# Folder to store album art
ALBUM_ART_FOLDER = 'album_art'

# Home page with basic UI
@app.route('/')
def home():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Spotify Song Downloader</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { color: #1DB954; }
            .btn { 
                display: inline-block; 
                background: #1DB954; 
                color: white; 
                padding: 10px 15px; 
                text-decoration: none; 
                border-radius: 4px;
                margin: 10px 0;
            }
            .steps { margin-top: 20px; }
            .step { margin-bottom: 15px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Spotify Song Downloader</h1>
            <p>A tool to retrieve and download your saved Spotify tracks</p>
            
            <div class="steps">
                <div class="step">
                    <h3>Step 1: Connect to Spotify</h3>
                    <a href="/login" class="btn">Login with Spotify</a>
                </div>
                
                <div class="step">
                    <h3>Step 2: Get Your Saved Tracks</h3>
                    <a href="/getTracksAndUrls" class="btn">Retrieve Tracks & URLs</a>
                    <p><small>This will retrieve all your saved tracks and their Spotify URLs</small></p>
                </div>
                
                <div class="step">
                    <h3>Step 3: Start Converting</h3>
                    <a href="/start_conversion" class="btn">Convert to MP3</a>
                    <p><small>This will start the MP3 conversion process</small></p>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(html)

# Spotify authentication
@app.route('/login')
def login():
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE
    )
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/authorize')
def authorize():
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE
    )
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['access_token'] = token_info['access_token']
    return redirect('/')

# Get tracks and URLs directly
@app.route('/getTracksAndUrls')
def getTracksAndUrls():
    if 'access_token' not in session:
        return redirect('/login')

    access_token = session.get('access_token')
    sp = spotipy.Spotify(auth=access_token)
    track_info = []
    spotify_urls = []
    iter = 0

    try:
        while True:
            offset = iter * 50
            iter += 1
            curGroup = sp.current_user_saved_tracks(limit=50, offset=offset)['items']
            
            if not curGroup:
                break
                
            for idx, item in enumerate(curGroup):
                track = item['track']
                song_name = track['name']
                artist_name = track['artists'][0]['name']
                formatted_name = f"{song_name} - {artist_name}"
                spotify_url = track['external_urls']['spotify']
                
                track_info.append({"song": formatted_name, "url": spotify_url})
                spotify_urls.append(spotify_url)
                
                print(f"Processing: {formatted_name} | URL: {spotify_url}")
            
            if len(curGroup) < 50:
                break
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.1)

        # Save track information to CSV
        df = pd.DataFrame([item["song"] for item in track_info])
        df.to_csv(CSV_FILE_PATH, index=False)
        
        # Save URLs to a file
        with open(SPOTIFY_URLS_FILE, 'w') as file:
            for url in spotify_urls:
                file.write(url + '\n')

    except Exception as e:
        print(f"Error retrieving tracks: {e}")

    return redirect('/')

# Start conversion process
@app.route('/start_conversion')
def start_conversion():
    def run_conversion():
        # Trigger the subprocess to start downloading and converting audio
        subprocess.run(['python', 'spotdl_script.py'])
    
    # Run conversion in a separate thread to avoid blocking Flask
    thread = Thread(target=run_conversion)
    thread.start()

    return jsonify({"status": "Conversion started"}), 200

def main():
    app.run(debug=True)

if __name__ == '__main__':
    main()
