import requests
import json
import os
import configparser
from urllib.request import urlopen

# --- Configuration Constants ---
YTS_CONFIG_FILE = "yts_domains.json"
APP_CONFIG_FILE = "config.ini"


class APIHandler:
    def __init__(self):
        self.yts_active_domain = None
        self.yts_domains = self._load_yts_domains()
        self.tmdb_api_key = None
        self._load_app_config()

    def _load_yts_domains(self):
        if not os.path.exists(YTS_CONFIG_FILE):
            defaults = ["https://yts.bz", "https://yts.gg", "https://yts.lt", "https://yts.am", "https://yts.ag"]
            with open(YTS_CONFIG_FILE, 'w') as f:
                json.dump(defaults, f, indent=4)
            return defaults
        try:
            with open(YTS_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _load_app_config(self):
        config = configparser.ConfigParser()
        if not os.path.exists(APP_CONFIG_FILE):
            config_content = (
                "# --- Movie Explorer Configuration ---\n\n"
                "# To enable enhanced features like trailers, cast info, and better ratings,\n"
                "# you need a FREE API key from The Movie Database (TMDB).\n\n"
                "# 1. Register for a free account at: https://www.themoviedb.org/signup\n"
                "# 2. Go to your account settings, find the 'API' section.\n"
                "# 3. Request an API key (it's usually approved instantly).\n"
                "# 4. Copy the 'API Key (v3 auth)' and paste it below, or add it via the in-app settings.\n\n"
                "[TMDB]\n"
                "api_key = \n"
            )
            with open(APP_CONFIG_FILE, 'w') as f:
                f.write(config_content)
        try:
            config.read(APP_CONFIG_FILE)
            key = config.get('TMDB', 'api_key', fallback=None)
            if key and key.strip():
                self.tmdb_api_key = key.strip()
                print("TMDB API Key loaded. Enhanced features are ENABLED.")
            else:
                self.tmdb_api_key = None
                print("No TMDB API Key found. Enhanced features are DISABLED.")
        except Exception as e:
            print(f"Error reading config file: {e}")

    def reload_yts_domains(self):
        self.yts_domains = self._load_yts_domains()
        self.yts_active_domain = None

    def reload_app_config(self):
        self._load_app_config()

    def _find_yts_active_domain(self):
        for domain in self.yts_domains:
            domain = domain.strip().rstrip('/')
            if not domain: continue
            try:
                response = requests.get(f"{domain}/api/v2/list_movies.json?limit=1", timeout=4)
                if response.status_code == 200 and response.json().get('status') == 'ok':
                    self.yts_active_domain = domain
                    return domain
            except requests.RequestException:
                continue
        return None

    def _make_yts_request(self, endpoint, params=None):
        if not self.yts_active_domain:
            if not self._find_yts_active_domain():
                raise ConnectionError("No active YTS domains found.")
        url = f"{self.yts_active_domain}/api/v2/{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get('status') == 'ok':
                return data.get('data')
            else:
                raise Exception(data.get('status_message', 'Unknown YTS API error'))
        except requests.RequestException as e:
            self.yts_active_domain = None
            raise ConnectionError(f"YTS network request failed: {e}") from e

    def list_movies(self, **kwargs):
        params = {'limit': 50}
        params.update(kwargs)
        return self._make_yts_request('list_movies.json', params)

    def get_movie_details(self, movie_id):
        params = {'movie_id': movie_id, 'with_images': 'true', 'with_cast': 'true'}
        return self._make_yts_request('movie_details.json', params)

    def get_tmdb_details(self, imdb_id):
        if not self.tmdb_api_key:
            return None
        try:
            find_url = f"https://api.themoviedb.org/3/find/{imdb_id}"
            params = {'api_key': self.tmdb_api_key, 'external_source': 'imdb_id'}
            response = requests.get(find_url, params=params, timeout=5)
            response.raise_for_status()
            find_data = response.json()
            if not find_data.get('movie_results'):
                return None
            tmdb_id = find_data['movie_results'][0]['id']
            details_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
            params = {'api_key': self.tmdb_api_key, 'append_to_response': 'videos,credits'}
            response = requests.get(details_url, params=params, timeout=5)
            response.raise_for_status()
            details_data = response.json()
            enhanced_data = {}
            if details_data.get('videos', {}).get('results'):
                for video in details_data['videos']['results']:
                    if video['type'].lower() == 'trailer' and video['site'].lower() == 'youtube':
                        enhanced_data['trailer_key'] = video['key']
                        break
            if details_data.get('credits', {}).get('cast'):
                enhanced_data['cast'] = [actor['name'] for actor in details_data['credits']['cast'][:5]]
            return enhanced_data
        except (requests.RequestException, KeyError, IndexError) as e:
            print(f"TMDB API request failed: {e}")
            return None

    def get_image_data(self, url):
        # Define a browser-like User-Agent to bypass 403 Forbidden errors
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            # Use requests.get with headers instead of urlopen
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.content # Return binary image data
            else:
                print(f"Image download failed. Status: {response.status_code} URL: {url}")
                return None
        except Exception as e:
            print(f"Failed to download image from {url}: {e}")
            return None
