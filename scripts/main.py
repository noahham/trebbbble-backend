import os
import time
import hmac
import hashlib
import base64
import requests
import urllib.parse
import yt_dlp
from PIL import Image
from io import BytesIO
import numpy as np

def download_video(url: str, error: list) -> None:
    """
    Scrapes video from either Reels, YT Shorts, or TikTok and writes to working directory.

    Args:
        url (str): URL to video from Reels, YT Shorts, or TikTok.
        error (list): List to store error messages.
    """

    try:
        if "youtube.com" in url or "youtu.be" in url:
            if "shorts" not in url:  # YouTube Shorts only
                print("Not a YouTube Shorts link.")
                error.append("Only YouTube SHORTS links are supported at the moment.")
                return

        # Write IG_COOKIES to a temp file if present
        cookies_file = None
        ig_cookies = os.getenv("IG_COOKIES")
        if ig_cookies:
            cookies_file = "cookies.txt"
            with open(cookies_file, "w") as f:
                f.write(ig_cookies)

        # yt-dlp options
        ydl_opts = {
            "outtmpl": os.path.join("output", "temp.%(ext)s"),  # Ensure correct extension
            "format": "bestaudio/best",  # Get the best audio format available
            "quiet": True,  # Suppress logs
            "noprogress": True,  # Hide progress bar
            "overwrites": True,  # Overwrite existing file
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",  # Convert to WAV
                "preferredquality": "0"  # Best quality
            }],
        }

        if cookies_file:
            ydl_opts["cookiefile"] = cookies_file  # Pass cookies to yt-dlp

        print(f"Downloading video...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        print("Download successful.")

        # Cleanup
        if cookies_file:
            os.remove(cookies_file)  # Remove temp cookies file

    except Exception as e:
        error.append("Invalid URL. Please enter a valid TikTok, Instagram Reels, or YouTube Shorts URL.")
        print(f"Error: {e}")

def recognize_song(error: list) -> tuple:
    """
    Recognizes song from WAV file.

    Returns:
        (str): Song title.
        (str): Song artist.
    """

    url = f"https://{os.environ.get('ACR_HOST')}/v1/identify"

    timestamp = str(int(time.time()))
    http_method = "POST"
    http_uri = "/v1/identify"
    signature_version = "1"

    string_to_sign = f"{http_method}\n{http_uri}\n{os.environ.get('ACR_CLIENT')}\naudio\n{signature_version}\n{timestamp}"
    signature = base64.b64encode(hmac.new(os.environ.get('ACR_SECRET').encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")

    data = {
        "access_key": os.environ.get('ACR_CLIENT'),
        "sample_bytes": os.path.getsize("output/temp.wav"),
        "timestamp": timestamp,
        "signature": signature,
        "data_type": "audio",
        "signature_version": "1"
    }

    print("Analyzing song...")

    # Read WAV file as binary
    with open("output/temp.wav", "rb") as f:
        files = {"sample": f}
        response = requests.post(url, data=data, files=files)

    # Parse response
    result = response.json()
    os.remove("output/temp.wav")
    if "metadata" in result and "music" in result["metadata"]:
        song_data = result["metadata"]["music"][0]
        print("Song found.")
        return song_data["title"], song_data["artists"][0]["name"]
    error.append("NO_SONG_FOUND")
    return None, None

def get_album_cover(title: str, artist: str) -> bool:
    """
    Gets an album cover given a song's title and artist using the iTunes API.

    Args:
        title (str): The name of the song.
        artist (str): The name of the artist.

    Returns:
        (bool) True if the album cover was found and saved, False otherwise.
    """
    base_url = "https://itunes.apple.com/search"

    # Parameters for search
    params = {
        "term": f"{title} {artist}",
        "media": "music",
        "limit": 1
    }

    try:
        # Fetches request
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        if data["resultCount"] > 0:
            album_cover_url = data["results"][0].get("artworkUrl100", "").replace("100x100bb", "1200x1200bb")
            if album_cover_url:
                image_response = requests.get(album_cover_url, stream=True)
                image_response.raise_for_status()

                image = Image.open(BytesIO(image_response.content))
                image = image.resize((300, 300), Image.BICUBIC)

                image.save("../media/cover.jpg", "JPEG")

                print("Album cover saved.")
                return True

        print("No album cover found.")
        return False

    except requests.RequestException as e:
        print(f"Error fetching album cover: {e}")
        return False

def get_color() -> str:
    """
    Analyzes a JPG image and returns the most vibrant color.

    Returns:
         str: String representing the most vibrant color in HEX format, or None if the image does not exist.
    """

    if os.path.exists("../media/cover.jpg"):
        image = Image.open("../media/cover.jpg").convert("RGB")
        pixels = np.array(image)

        # Flattens to (R, G, B)
        pixels = pixels.reshape((-1, 3))

        # Compute the sum of squared differences from grayscale and gets max
        grayscale = np.mean(pixels, axis=1, keepdims=True)
        vibrancy = np.sum((pixels - grayscale) ** 2, axis=1)
        most_vibrant_idx = np.argmax(vibrancy)
        most_vibrant_color = tuple(pixels[most_vibrant_idx])

        # Converts to HEX
        return "#{:02X}{:02X}{:02X}".format(*most_vibrant_color)
    else:
        return "NO_COLOR"

def get_text_color(hex_color: str):
    """
    Determines whether white or black text provides better readability on a given background color.

    Args:
        hex_color (str): Hex color string.

    Returns:
        str: "#FFFFFF" for white text or "#000000" for black text
    """
    if hex_color == "NO_COLOR":
        return "#000000"

    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)

    # Calculate Relative luminance
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255

    return "#FFFFFF" if luminance < 0.5 else "#000000"

def get_song_urls(title: str, artist: str) -> tuple:
    """
    Generates a Spotify, YouTube Music, and Apple Music search link for the given song title and artist.

    Args:
        title (str): The title of the song.
        artist (str): The artist of the song.

    Returns:
        tuple: Spotify, YouTube Music, and Apple Music search links.
    """

    query = f"{title} {artist}"
    encoded_query = urllib.parse.quote(query)

    return (
        f"https://open.spotify.com/search/{encoded_query}",
        f"https://music.youtube.com/search?q={encoded_query}",
        f"https://music.apple.com/us/search?term={encoded_query}"
        )

def generate_output(title: str, artist: str, cover: bool, color: str, error: list) -> dict:
    """
    Tries to make a dictionary with the song data.

    Args:
        title (str): The title of the song.
        artist (str): The artist of the song.
        cover (bool): Whether the album cover was found.
        color (str): The most vibrant color in the album cover.
        error (list): List to store error messages.

    Returns:
        dict: A dictionary containing the song data.
    """

    if title and artist:
        urls = get_song_urls(title, artist)
        text_color = get_text_color(color)
        return {
            "success": True,
            "title": title,
            "artist": artist,
            "cover": cover,
            "color": color,
            "text_color": text_color,
            "spotify": urls[0],
            "youtube": urls[1],
            "apple": urls[2]
        }
    else:
        return {
            "success": False,
            "error": error[0]
        }

def main(url):
    error_msg = []
    t, a = None, None
    cover = False
    color = "NO_COLOR"

    # Generating WAV file
    download_video(url, error_msg)

    # Retrieving and return song data if no errors
    if len(error_msg) == 0:
        t, a = recognize_song(error_msg)
        cover = get_album_cover(t, a)
        color = get_color()

    return generate_output(t, a, cover, color, error_msg)

if __name__ == "__main__":
    print(main("https://www.instagram.com/reels/DHNIsklRe-Y/")) # Change URL to test