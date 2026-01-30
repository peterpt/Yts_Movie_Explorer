import requests
import json
import os
import configparser
import threading
import time

# --- Configuration Constants ---
YTS_CONFIG_FILE = "yts_domains.json"
APP_CONFIG_FILE = "config.ini"


class APIHandler:
    def __init__(self):
        self.yts_active_domain = None
        self.yts_domains = self._load_yts_domains()
        self.tmdb_api_key = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self._load_app_config()

    def _load_yts_domains(self):
        if not os.path.exists(YTS_CONFIG_FILE):
            defaults = ["https://yts.mx", "https://yts.bz", "https://yts.lt", "https://yts.am", "https://yts.ag"]
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
            config_content = "[TMDB]\napi_key = \n"
            with open(APP_CONFIG_FILE, 'w') as f:
                f.write(config_content)
        try:
            config.read(APP_CONFIG_FILE)
            key = config.get('TMDB', 'api_key', fallback=None)
            self.tmdb_api_key = key.strip() if key and key.strip() else None
        except Exception as e:
            print(f"Error reading config file: {e}")

    def reload_yts_domains(self):
        self.yts_domains = self._load_yts_domains()
        self.yts_active_domain = None

    def reload_app_config(self):
        self._load_app_config()

    def _test_domain_speed(self, domain, results_list):
        """Worker function for threading. Tests a single domain and records its speed."""
        try:
            url = f"{domain.strip().rstrip('/')}/api/v2/list_movies.json?limit=1"
            print(f"  -> Testing {domain}...")
            start_time = time.monotonic()
            
            # --- CHANGE: Increased test timeout to 20 seconds ---
            response = requests.get(url, headers=self.headers, timeout=20)
            
            if response.status_code == 200:
                if response.json().get('status') == 'ok':
                    latency = time.monotonic() - start_time
                    print(f"  [SUCCESS] {domain} responded in {latency:.2f} seconds.")
                    results_list.append((latency, domain))
                else:
                    print(f"  [FAILED] {domain} responded but API status is not 'ok'.")
            else:
                print(f"  [FAILED] {domain} returned HTTP status code {response.status_code}.")

        except requests.exceptions.RequestException as e:
            print(f"  [FAILED] {domain} could not be reached. Reason: Timeout or connection error.")

    def _find_fastest_active_domain(self):
        """
        Tests all domains concurrently to find the one with the lowest latency.
        """
        print("Searching for the fastest YTS domain...")
        domain_latencies = []
        threads = []

        for domain in self.yts_domains:
            if domain.strip():
                thread = threading.Thread(target=self._test_domain_speed, args=(domain, domain_latencies))
                threads.append(thread)
                thread.start()

        for thread in threads:
            thread.join()

        print("-" * 30)
        if not domain_latencies:
            print("All domains failed the test.")
            return None

        domain_latencies.sort()
        fastest_domain = domain_latencies[0][1]
        fastest_time = domain_latencies[0][0]

        print(f"Found {len(domain_latencies)} working domains.")
        print(f"Fastest is {fastest_domain} ({fastest_time:.2f}s). Selecting it.")
        print("-" * 30)
        
        self.yts_active_domain = fastest_domain
        return fastest_domain

    def _make_yts_request(self, endpoint, params=None):
        if not self.yts_active_domain:
            if not self._find_fastest_active_domain():
                raise ConnectionError("No active YTS domains found.\n\nCheck your internet connection or edit the YTS Domains list in the app settings.")
        
        url = f"{self.yts_active_domain}/api/v2/{endpoint}"
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data.get('status') == 'ok':
                return data.get('data')
            else:
                raise Exception(data.get('status_message', 'Unknown YTS API error'))
        except requests.RequestException as e:
            self.yts_active_domain = None
            raise ConnectionError(f"Request to {url} failed. Re-scanning on next attempt. Error: {e}") from e

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
            response = requests.get(find_url, params=params, timeout=10)
            response.raise_for_status()
            find_data = response.json()
            if not find_data.get('movie_results'): return None
            
            tmdb_id = find_data['movie_results'][0]['id']
            details_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
            params = {'api_key': self.tmdb_api_key, 'append_to_response': 'videos,credits'}
            response = requests.get(details_url, params=params, timeout=10)
            response.raise_for_status()
            details_data = response.json()
            
            enhanced_data = {}
            if details_data.get('videos', {}).get('results'):
                for video in details_data['videos']['results']:
                    if video['type'].lower() == 'trailer' and video['site'].lower() == 'youtube':
                        enhanced_data['trailer_key'] = video['key']; break
            if details_data.get('credits', {}).get('cast'):
                enhanced_data['cast'] = [actor['name'] for actor in details_data['credits']['cast'][:10]]
            if details_data.get('overview'):
                enhanced_data['description_full'] = details_data['overview']
            return enhanced_data
        except (requests.RequestException, KeyError, IndexError) as e:
            print(f"TMDB API request failed: {e}"); return None

    def get_image_data(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=20)
            return response.content if response.status_code == 200 else None
        except Exception as e:
            print(f"Failed to download image from {url}: {e}"); return None
