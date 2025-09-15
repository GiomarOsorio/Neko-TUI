import cloudscraper
from bs4 import BeautifulSoup
from typing import List, Dict
from urllib.parse import quote
import re

class JKAnimeClient:
    """
    Client for interacting with jkanime.net.
    
    Provides methods to:
    - Fetch recent trending anime
    - Search anime by query
    - Get detailed information about a specific anime
    - Extract streaming URLs for specific episodes
    """

    BASE_URL = "https://jkanime.net"
    SEACH_PATH = "buscar"
    RECENTS_PATHS = {
        "animes": "#animes",
        "donghuas": "#donghuas",
        "ovas": "#ovas"
    }
    EPISODE_URL_EXTRACTOR_PATTERN = r'<iframe[^>]*class="player_conte"[^>]*src="([^"]+)"'

    def __init__(self):
        """
        Initialize the JKAnime client with a cloudscraper session.
        Sets custom headers to mimic a real browser request.
        """
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.headers = {
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Referer": self.BASE_URL
        }

    def get_recent(self) -> List[Dict]:
        """
        Fetch the trending/recent anime from the homepage.

        Returns:
            List[Dict]: A list of dictionaries containing
            'title', 'thumbnail', 'url', 'type', and 'status'.
        """
        trending_anime_data = []
        r = self.scraper.get(f"{self.BASE_URL}", headers=self.headers)
        r.raise_for_status()
        bs4_soup = BeautifulSoup(r.text, 'html.parser')

        # Select the trending anime divs
        trending_anime_divs = (bs4_soup.find_all('div', class_='trending_div')[0]).find_all('div', class_='p-3')

        for trending_anime_div in trending_anime_divs:
            trending_anime_data.append({
                "status": trending_anime_div.find('p').text.strip(),
                "thumbnail": trending_anime_div.find('img').get('src').strip(),
                "title": trending_anime_div.find('h5').text.strip(),
                "type": trending_anime_div.find_all('p')[1].text.strip(),
                "url": trending_anime_div.find('h5').find('a').get('href').strip(),
            })
        return trending_anime_data

    def search(self, query: str) -> List[Dict]:
        """
        Search for anime based on a query string.

        Args:
            query (str): Search term.

        Returns:
            List[Dict]: List of dictionaries containing 'title', 'thumbnail',
            'url', 'type', and 'status' for each matching anime.
        """
        search_anime_data = []
        r = self.scraper.get(f"{self.BASE_URL}/{self.SEACH_PATH}/{quote(query)}", headers=self.headers)
        r.raise_for_status()
        bs4_soup = BeautifulSoup(r.text, 'html.parser')
        search_anime_divs = bs4_soup.find_all('div', class_='anime__item')

        for search_anime_div in search_anime_divs:
            search_anime_data.append({
                "status": search_anime_div.find_all('li')[0].text.strip(),
                "thumbnail": search_anime_div.find('div', class_='anime__item__pic').get('data-setbg').strip(),
                "title": search_anime_div.find('h5').text.strip(),
                "type": search_anime_div.find_all('li')[1].text.strip(),
                "url": search_anime_div.find('h5').find('a').get('href').strip(),
            })
        return search_anime_data

    def get_anime_details(self, anime_url: str) -> Dict:
        """
        Fetch detailed information about a specific anime.

        Args:
            anime_url (str): Full URL of the anime page.

        Returns:
            Dict: Dictionary containing:
                - 'title', 'synopsis', 'thumbnail', 'type'
                - 'genres', 'studios', 'temp', 'status'
                - 'episodes': list of episodes with 'name' and 'url'
        """
        r = self.scraper.get(anime_url, headers=self.headers)
        r.raise_for_status()
        bs4_soup = BeautifulSoup(r.text, 'html.parser')

        anime_details = bs4_soup.find('div', class_='anime__details__content')
        title = anime_details.find('div', class_='anime_info').find('h3').text.strip()
        synopsis = anime_details.find('div', class_='anime_info').find('p').text.strip()
        thumbnail = anime_details.find('div', class_='anime_pic').find('img').get('src')
        anime_data = anime_details.find('div', class_='anime_data')

        genres = [{"name": a.text, "url": a.get('href')} for a in anime_data.find_all('li')[1].find_all('a')]
        anime_data_li = anime_details.find('div', class_="card-bod").find('ul').find_all('li')
        anime_type = anime_data_li[0].text.replace('Tipo: ', '')
        studios = [{"name": a_tag.text, "url": a_tag.get('href')} for a_tag in anime_data_li[2].find_all('a')]
        temp = [{"name": a_tag.text, "url": a_tag.get('href')} for a_tag in anime_data_li[3].find_all('a')][0]
        status = anime_data_li[-2].find('div').text

        # Determine total episodes
        last_episode = int(anime_details.find('a', id='uep').text.strip().split('-')[1].strip().split(' ')[0])
        episodes = [{"name": f"Capítulo {i}", "url": f"{anime_url}{i}/"} for i in range(1, last_episode + 1)]

        return {
            "episodes": episodes,
            "genres": genres,
            "synopsis": synopsis,
            "status": status,
            "studios": studios,
            "temp": temp,
            "thumbnail": thumbnail,
            "title": title,
            "type": anime_type,
        }

    def get_episode_stream(self, episode_url: str) -> List[Dict]:
        """
        Extract streaming URLs from a given episode page.

        Args:
            episode_url (str): Full URL of the episode page.

        Returns:
            List[Dict]: List of dictionaries containing 'index' and 'src' of each video iframe.
                        The last iframe is excluded by default.
        """
        seen = set()
        episode_streams = []
        r = self.scraper.get(episode_url, headers=self.headers)
        r.raise_for_status()
        matches = re.findall(self.EPISODE_URL_EXTRACTOR_PATTERN, r.text)

        for i, url in enumerate(matches[:-1]):
            r = self.scraper.get(url, headers=self.headers)
            bs4_soup = BeautifulSoup(r.text, 'html.parser')

            if bs4_soup.find('source'):
                video_src= bs4_soup.find('source').get('src')
                episode_streams.append({"index": i, "src": video_src})
            else:
                scripts = bs4_soup.find_all("script")
                for script in scripts:
                    if script.string:
                        match = re.search(r"url:\s*'([^']+\.m3u8)'", script.string)
                        if match:
                            episode_streams.append({"index": i, "src": match.group(1)})
                            break

        episode_streams = [d for d in episode_streams if not (d['src'] in seen or seen.add(d['src']))]
        return episode_streams
