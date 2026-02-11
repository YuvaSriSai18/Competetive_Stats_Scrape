"""
Shared configuration and utilities for GFG Scraper
"""

import sys
import asyncio

# Fix for Windows asyncio subprocess issues with Playwright
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from typing import Dict
import httpx
from bs4 import BeautifulSoup
import re
from playwright.async_api import async_playwright

# ======================================================
# CONFIG
# ======================================================

# GeeksForGeeks Submissions API
GFG_SUBMISSION_API = "https://practiceapi.geeksforgeeks.org/api/v1/user/problems/submissions/"
GFG_PROFILE_PAGE = "https://www.geeksforgeeks.org/user/{username}/"

# Control concurrency (important to avoid rate limit)
MAX_CONCURRENT_REQUESTS = 10
BATCH_SIZE = 10  # Process 10 users per batch

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.geeksforgeeks.org/"
}

# ======================================================
# SHARED FUNCTIONS
# ======================================================

def parse_submission_data(data: Dict):
    """Parse GFG API response data"""
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
        "count_field": data.get("count")
    }


async def fetch_user(client: httpx.AsyncClient, username: str, sem):
    """Fetch submission data for a single user"""
    async with sem:
        payload = {
            "handle": username,
            "requestType": "",
            "year": "",
            "month": ""
        }
        
        try:
            res = await client.post(GFG_SUBMISSION_API, json=payload, timeout=20)
            
            if res.status_code != 200:
                return {
                    "user": username,
                    "error": f"status {res.status_code}"
                }
            
            data = res.json()
            parsed = parse_submission_data(data)
            
            return {
                "user": username,
                **parsed
            }
        
        except Exception as e:
            return {
                "user": username,
                "error": str(e)
            }


async def create_browser():
    """Create a Playwright browser instance for reuse"""
    playwright_instance = await async_playwright().start()
    browser = await playwright_instance.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ]
    )
    return browser, playwright_instance


async def scrape_profile_page_with_page(page, username: str):
    """Scrape profile page using Playwright page to extract all user data"""
    profile_data = {}
    
    try:
        url = GFG_PROFILE_PAGE.format(username=username)
        await page.goto(url, wait_until="networkidle", timeout=30000)
        
        # Wait for profile container to be present
        try:
            await page.wait_for_selector(".NewProfile_profileContainer__G__Lh", timeout=10000)
        except:
            pass  # Continue anyway if wait fails
        
        # Get page content after JS rendering
        content = await page.content()
        soup = BeautifulSoup(content, 'lxml')
        
        # Extract Full Name from h2 with specific class
        try:
            name_elem = soup.find('h2', class_='NewProfile_name__N_Nlw')
            if name_elem:
                fullname = name_elem.get_text(strip=True)
                profile_data['fullName'] = fullname
        except Exception as e:
            pass
        
        # Extract Profile Picture URL
        try:
            img_elem = soup.find('img', class_=re.compile(r'rounded-full', re.I))
            
            if img_elem and img_elem.get('src'):
                src = img_elem['src']
                # Convert to full URL if relative
                if src.startswith('http'):
                    profile_data['profilePicture'] = src
                elif src.startswith('/'):
                    profile_data['profilePicture'] = 'https://www.geeksforgeeks.org' + src
                else:
                    profile_data['profilePicture'] = 'https://www.geeksforgeeks.org/' + src
        except Exception as e:
            pass
        
        # Extract Institute Name from Qualifications section
        try:
            qualifications = soup.find('div', class_=re.compile(r'[Qq]ualification', re.I))
            if qualifications:
                p_tag = qualifications.find('p')
                if p_tag:
                    institute_text = p_tag.get_text(strip=True)
                    if institute_text and len(institute_text) < 100:
                        profile_data['institute'] = institute_text
        except Exception as e:
            pass
        
        # Extract Coding Score using CSS class selector
        try:
            score_elements = soup.find_all(class_="ScoreContainer_value__7yy7h")
            if len(score_elements) > 0:
                score_text = score_elements[0].get_text(strip=True)
                score_match = re.search(r'(\d+)', score_text)
                if score_match:
                    profile_data['codingScore'] = int(score_match.group(1))
        except:
            pass
        
        # Extract Institute Rank (should be 3rd score card)
        try:
            score_elements = soup.find_all(class_="ScoreContainer_value__7yy7h")
            if len(score_elements) > 2:
                rank_text = score_elements[2].get_text(strip=True)
                rank_match = re.search(r'(\d+)', rank_text)
                if rank_match:
                    profile_data['instituteRank'] = int(rank_match.group(1))
        except:
            pass
        
        # Extract Max Streak (Longest Streak) using POTD container
        try:
            streak_values = soup.find_all(class_="PotdContainer_statValue__nt1dr")
            if len(streak_values) > 0:
                max_streak_text = streak_values[0].get_text(strip=True)
                max_streak_match = re.search(r'(\d+)', max_streak_text)
                if max_streak_match:
                    profile_data['maxStreak'] = int(max_streak_match.group(1))
        except:
            pass
        
        # Extract Current POTD Streak from text like "0 Day POTD Streak"
        try:
            potd_text_elem = soup.find(string=re.compile(r'\d+\s*Day\s*POTD\s*Streak', re.I))
            if potd_text_elem:
                potd_text = potd_text_elem.get_text(strip=True)
                potd_match = re.search(r'(\d+)\s*Day', potd_text, re.I)
                if potd_match:
                    profile_data['currentStreak'] = int(potd_match.group(1))
        except:
            pass
    
    except Exception as e:
        pass
    
    return profile_data


async def fetch_user_complete(client: httpx.AsyncClient, username: str, sem, page=None):
    """Fetch complete user data: submissions + UI scraping
    
    Args:
        client: httpx async client
        username: GFG username
        sem: asyncio semaphore for rate limiting
        page: Optional Playwright page instance (if provided, reuses it instead of creating new one)
    """
    async with sem:
        try:
            # Fetch submissions from API
            submissions_data = await fetch_user(client, username, asyncio.Semaphore(1))
            
            # Check if submissions failed
            if "error" in submissions_data:
                return submissions_data
            
            # Scrape profile page UI (gets fullName, profilePicture, institute, codingScore, scores, streaks)
            if page:
                # Reuse existing page
                ui_data = await scrape_profile_page_with_page(page, username)
            else:
                # Create new browser for single request (fallback)
                browser, playwright_instance = await create_browser()
                try:
                    new_page = await browser.new_page()
                    ui_data = await scrape_profile_page_with_page(new_page, username)
                finally:
                    await new_page.close()
                    await browser.close()
                    await playwright_instance.stop()
            
            # Combine all data
            complete_data = {
                "user": username,
                **submissions_data,
                **ui_data
            }
            
            return complete_data
        
        except Exception as e:
            return {
                "user": username,
                "error": str(e)
            }
