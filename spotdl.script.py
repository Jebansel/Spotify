import os
import sys
import subprocess
import requests
from bs4 import BeautifulSoup
import urllib.parse
from PIL import Image
from io import BytesIO
import time
import random

# First, check and install required packages
def ensure_package_installed(package_name):
    try:
        __import__(package_name)
        print(f"{package_name} is already installed.")
    except ImportError:
        print(f"{package_name} not found. Installing {package_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"{package_name} has been installed.")

# Ensure spotdl is installed
ensure_package_installed("spotdl")

# Now import spotdl (after we've ensured it's installed)
from spotdl import Spotdl, Song

# Folder to store album art
ALBUM_ART_FOLDER = 'album_art'

def get_album_art(song_info):
    """Search Google Images for album art based on song info"""
    # Extract info from song metadata
    title = song_info.name if hasattr(song_info, 'name') else ''
    artist = song_info.artists[0] if hasattr(song_info, 'artists') and song_info.artists else ''
    album = song_info.album_name if hasattr(song_info, 'album_name') else ''
    
    # Create a more specific search query for album art
    if album and artist:
        search_query = f"{artist} {album} album cover"
    elif artist and title:
        search_query = f"{artist} {title} album cover"
    else:
        # Fallback to title only
        search_query = f"{title} album cover"
    
    print(f"Searching for album art using query: {search_query}")
    
    encoded_query = urllib.parse.quote(search_query)
    url = f"https://www.google.com/search?q={encoded_query}&tbm=isch"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find image links in the page
        img_tags = soup.find_all('img')
        img_urls = []
        
        for img in img_tags:
            if img.has_attr('src') and 'http' in img['src'] and 'google' not in img['src'].lower():
                img_urls.append(img['src'])
        
        # Skip the first image as it's often a Google icon
        if len(img_urls) > 1:
            album_art_url = img_urls[1]  # Use the second image which is typically the most relevant result
            
            # Download the image
            img_response = requests.get(album_art_url)
            if img_response.status_code == 200:
                # Create album art directory if it doesn't exist
                os.makedirs(ALBUM_ART_FOLDER, exist_ok=True)
                
                # Create a safe filename based on the search query
                safe_filename = "".join(c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in search_query)
                filename = f"{ALBUM_ART_FOLDER}/{safe_filename[:50]}.jpg"
                
                # Check and resize the image to ensure it's suitable for album art
                try:
                    image = Image.open(BytesIO(img_response.content))
                    # Resize to a standard album art size if needed
                    if image.width != image.height:
                        # Make it square by taking the min dimension
                        size = min(image.width, image.height)
                        # Calculate coordinates for center crop
                        left = (image.width - size) // 2
                        top = (image.height - size) // 2
                        right = left + size
                        bottom = top + size
                        image = image.crop((left, top, right, bottom))
                    
                    # Resize to a standard size for album art
                    image = image.resize((500, 500))
                    image.save(filename)
                    print(f"Found and saved album art: {filename}")
                    return filename
                except Exception as e:
                    print(f"Error processing image: {e}")
                    return None
            else:
                print(f"Failed to download image, status code: {img_response.status_code}")
        else:
            print("No suitable images found")
    except Exception as e:
        print(f"Error searching for album art: {e}")
    
    return None

def download_and_convert_audio(spotify_url, output_folder):
    """Download a Spotify track using spotdl and add custom album art"""
    try:
        # Initialize spotdl
        # Note: In newer versions of spotdl, client_id and client_secret might be optional
        # as spotdl can use its default credentials
        spotify_dl = Spotdl(
            output_format="mp3",
            bitrate="320k",
        )
        
        # Get song info from Spotify URL
        songs = spotify_dl.search([spotify_url])
        if not songs:
            raise Exception("No songs found for the given URL")
        
        song = songs[0]
        
        # Use spotdl to download the song
        print(f"Downloading: {song.name} by {', '.join(song.artists)}")
        download_info = spotify_dl.download(songs, output_folder)
        
        # Get the downloaded file path
        if not download_info or not download_info[0]:
            raise Exception("Download failed")
        
        # The path to the downloaded file
        mp3_filename = download_info[0]
        
        # Search for album art
        print("Searching for proper album art...")
        album_art_path = get_album_art(song)
        
        # If no album art found or error occurred, use Spotify thumbnail
        if not album_art_path:
            print("Using Spotify thumbnail as fallback")
            use_spotify_thumbnail = True
        else:
            print(f"Using custom album art: {album_art_path}")
            use_spotify_thumbnail = False
        
        # If we found custom album art, add it to the MP3
        if not use_spotify_thumbnail and album_art_path and os.path.exists(mp3_filename):
            try:
                # Using ffmpeg to add album art
                temp_filename = mp3_filename + '.temp.mp3'
                subprocess.run([
                    'ffmpeg', '-i', mp3_filename, 
                    '-i', album_art_path, 
                    '-map', '0:0', '-map', '1:0', 
                    '-c', 'copy', '-id3v2_version', '3',
                    '-metadata:s:v', 'title="Album cover"', 
                    '-metadata:s:v', 'comment="Cover (front)"',
                    temp_filename
                ])
                
                # Replace original file with the one with album art
                os.replace(temp_filename, mp3_filename)
                print(f"Added custom album art to {os.path.basename(mp3_filename)}")
            except Exception as e:
                print(f"Error adding album art: {e}")
        
        return song.name
    except Exception as e:
        print(f"Error downloading {spotify_url}: {str(e)}")
        raise e

def process_urls_from_file(file_path, output_folder):
    """Process multiple Spotify URLs from a text file"""
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Read URLs from the file and download each one
    with open(file_path, 'r') as file:
        urls = file.readlines()
    
    # Remove any extra whitespace or newlines
    urls = [url.strip() for url in urls if url.strip()]

    # Track results
    successes = []
    failures = []

    # Process each URL
    for i, url in enumerate(urls):
        try:
            print(f"\nProcessing [{i+1}/{len(urls)}]: {url}")
            title = download_and_convert_audio(url, output_folder)
            successes.append((url, title))
            print(f"Successfully downloaded: {title}")
            
            # Add a small delay between requests to avoid rate limiting
            if i < len(urls) - 1:
                delay = random.uniform(1.5, 3.0)
                print(f"Waiting {delay:.1f} seconds before next download...")
                time.sleep(delay)
        except Exception as e:
            print(f"Error downloading {url}: {str(e)}")
            failures.append((url, str(e)))
    
    # Print summary
    print("\n===== Download Summary =====")
    print(f"Total URLs: {len(urls)}")
    print(f"Successful downloads: {len(successes)}")
    print(f"Failed downloads: {len(failures)}")
    
    if failures:
        print("\nFailed URLs:")
        for url, error in failures:
            print(f"- {url}: {error}")

def main():
    # Path to the text file containing Spotify URLs (one per line)
    urls_file = 'spotify_urls.txt'  # Replace with your text file path
    output_folder = 'C:/Users/Jeban/Music/MP3s'  # Replace with your desired output folder path
    
    # Ensure required packages are installed
    ensure_package_installed("requests")
    ensure_package_installed("beautifulsoup4")
    ensure_package_installed("pillow")
    
    # Check if ffmpeg is installed
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("ffmpeg is already installed.")
    except FileNotFoundError:
        print("WARNING: ffmpeg is not installed or not in PATH. Album art embedding may not work.")
        print("Please install ffmpeg and add it to your PATH.")
    
    process_urls_from_file(urls_file, output_folder)
    
    print("\nProcessing complete. Files are ready to be imported into iTunes.")

if __name__ == "__main__":
    main()
