"""
GFG Scraper - BeautifulSoup based (API + UI scraping)
"""

import asyncio
import logging
import json
from typing import Dict
import httpx
from bs4 import BeautifulSoup
import re

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================================================
# CONFIG
# ======================================================

GFG_SUBMISSION_API = "https://practiceapi.geeksforgeeks.org/api/v1/user/problems/submissions/"
GFG_PROFILE_PAGE = "https://www.geeksforgeeks.org/user/{username}/"

MAX_CONCURRENT_REQUESTS = 10
BATCH_SIZE = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.geeksforgeeks.org/"
}

# ======================================================
# SHARED FUNCTIONS
# ======================================================

def parse_api_response(response_text: str) -> Dict:
    """Parse API response (JSON string) using BeautifulSoup approach"""
    try:
        # Parse JSON response
        data = json.loads(response_text)
        result = data.get("result", {})
        
        basic = len(result.get("Basic", {}))
        easy = len(result.get("Easy", {}))
        medium = len(result.get("Medium", {}))
        hard = len(result.get("Hard", {}))
        
        return {
            "basic": basic,
            "easy": easy,
            "medium": medium,
            "hard": hard,
            "total": basic + easy + medium + hard,
        }
    except Exception as e:
        logger.error(f"Error parsing API response: {e}")
        return {"error": str(e)}


def scrape_profile_page(html_content: str, username: str) -> Dict:
    """Scrape profile page HTML using BeautifulSoup"""
    profile_data = {}
    
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Extract Full Name from h2 with specific class
        try:
            name_elem = soup.find('h2', class_='NewProfile_name__N_Nlw')
            if name_elem:
                fullname = name_elem.get_text(strip=True)
                profile_data['fullName'] = fullname
        except Exception as e:
            logger.debug(f"Could not extract fullName: {e}")
        
        # Extract Profile Picture URL
        try:
            img_elem = soup.find('img', class_=re.compile(r'rounded-full', re.I))
            if img_elem and img_elem.get('src'):
                src = img_elem['src']
                if src.startswith('http'):
                    profile_data['profilePicture'] = src
                elif src.startswith('/'):
                    profile_data['profilePicture'] = 'https://www.geeksforgeeks.org' + src
                else:
                    profile_data['profilePicture'] = 'https://www.geeksforgeeks.org/' + src
        except Exception as e:
            logger.debug(f"Could not extract profilePicture: {e}")
        
        # Extract Institute Name
        try:
            qualifications = soup.find('div', class_=re.compile(r'[Qq]ualification', re.I))
            if qualifications:
                p_tag = qualifications.find('p')
                if p_tag:
                    institute_text = p_tag.get_text(strip=True)
                    if institute_text and len(institute_text) < 100:
                        profile_data['institute'] = institute_text
        except Exception as e:
            logger.debug(f"Could not extract institute: {e}")
        
        # Extract Coding Score
        try:
            score_elements = soup.find_all(class_="ScoreContainer_value__7yy7h")
            if len(score_elements) > 0:
                score_text = score_elements[0].get_text(strip=True)
                score_match = re.search(r'(\d+)', score_text)
                if score_match:
                    profile_data['codingScore'] = int(score_match.group(1))
        except Exception as e:
            logger.debug(f"Could not extract codingScore: {e}")
        
        # Extract Institute Rank
        try:
            score_elements = soup.find_all(class_="ScoreContainer_value__7yy7h")
            if len(score_elements) > 2:
                rank_text = score_elements[2].get_text(strip=True)
                rank_match = re.search(r'(\d+)', rank_text)
                if rank_match:
                    profile_data['instituteRank'] = int(rank_match.group(1))
        except Exception as e:
            logger.debug(f"Could not extract instituteRank: {e}")
        
        # Extract Max Streak
        try:
            streak_values = soup.find_all(class_="PotdContainer_statValue__nt1dr")
            if len(streak_values) > 0:
                max_streak_text = streak_values[0].get_text(strip=True)
                max_streak_match = re.search(r'(\d+)', max_streak_text)
                if max_streak_match:
                    profile_data['maxStreak'] = int(max_streak_match.group(1))
        except Exception as e:
            logger.debug(f"Could not extract maxStreak: {e}")
        
        # Extract Current POTD Streak
        try:
            potd_text_elem = soup.find(string=re.compile(r'\d+\s*Day\s*POTD\s*Streak', re.I))
            if potd_text_elem:
                potd_text = potd_text_elem.get_text(strip=True)
                potd_match = re.search(r'(\d+)\s*Day', potd_text, re.I)
                if potd_match:
                    profile_data['currentStreak'] = int(potd_match.group(1))
        except Exception as e:
            logger.debug(f"Could not extract currentStreak: {e}")
    
    except Exception as e:
        logger.error(f"Error scraping profile page for {username}: {e}")
    
    return profile_data


async def fetch_user_complete(client: httpx.AsyncClient, username: str, sem) -> Dict:
    """Fetch complete user data: API + UI scraping using BeautifulSoup"""
    async with sem:
        try:
            # Step 1: Fetch API data
            logger.info(f"Fetching API data for {username}...")
            payload = {
                "handle": username,
                "requestType": "",
                "year": "",
                "month": ""
            }
            
            api_res = await client.post(GFG_SUBMISSION_API, json=payload, timeout=20)
            
            if api_res.status_code != 200:
                return {
                    "user": username,
                    "error": f"API error: status {api_res.status_code}"
                }
            
            api_data = parse_api_response(api_res.text)
            
            if "error" in api_data:
                return {
                    "user": username,
                    "error": api_data["error"]
                }
            
            # Step 2: Fetch profile page HTML and scrape with BeautifulSoup
            logger.info(f"Fetching profile page for {username}...")
            url = GFG_PROFILE_PAGE.format(username=username)
            
            profile_res = await client.get(url, timeout=20)
            
            if profile_res.status_code != 200:
                logger.warning(f"Profile page returned {profile_res.status_code} for {username}")
                profile_data = {}
            else:
                profile_data = scrape_profile_page(profile_res.text, username)
            
            # Combine all data
            complete_data = {
                "user": username,
                **api_data,
                **profile_data
            }
            
            logger.info(f"Successfully scraped user {username}")
            return complete_data
        
        except Exception as e:
            logger.error(f"Error fetching complete data for {username}: {e}")
            return {
                "user": username,
                "error": str(e)
            }
