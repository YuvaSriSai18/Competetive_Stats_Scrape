
import asyncio
import logging
import httpx
from fastapi import FastAPI, HTTPException

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from utils.config import (
    fetch_user_complete,
    HEADERS
)

app = FastAPI(title="GFG Scraper API", version="1.0.0")


# ======================================================
# FORMAT RESPONSE FUNCTION
# ======================================================

def format_gfg_response(raw_data: dict) -> dict:
    """Format raw GFG data into the required JSON structure"""
    
    if "error" in raw_data:
        return {
            "user": raw_data.get("user", ""),
            "error": raw_data["error"]
        }
    
    # Extract info fields
    info = {
        "userName": raw_data.get("user", ""),
        "fullName": raw_data.get("fullName", ""),
        "profilePicture": raw_data.get("profilePicture", ""),
        "institute": raw_data.get("institute", ""),
        "codingScore": raw_data.get("codingScore", 0),
        "maxStreak": raw_data.get("maxStreak", 0),
        "currentStreak": raw_data.get("currentStreak", 0),
        "instituteRank": raw_data.get("instituteRank", 0),
        "totalProblemsSolved": raw_data.get("total", 0),
    }
    
    # Remove None values and empty strings from info
    info = {k: v for k, v in info.items() if v is not None and v != ""}
    
    # Extract solvedStats fields
    solvedStats = {}
    
    if raw_data.get("basic", 0) > 0:
        solvedStats["basic"] = {"count": raw_data.get("basic", 0)}
    if raw_data.get("easy", 0) > 0:
        solvedStats["easy"] = {"count": raw_data.get("easy", 0)}
    if raw_data.get("medium", 0) > 0:
        solvedStats["medium"] = {"count": raw_data.get("medium", 0)}
    if raw_data.get("hard", 0) > 0:
        solvedStats["hard"] = {"count": raw_data.get("hard", 0)}
    if raw_data.get("school", 0) > 0:
        solvedStats["school"] = {"count": raw_data.get("school", 0)}
    
    return {
        "info": info,
        "solvedStats": solvedStats
    }


# ======================================================
# EXPORTABLE FUNCTION
# ======================================================

def get_gfg_stats(username: str) -> dict:
    """Get GFG stats for a user (synchronous wrapper)
    
    Args:
        username: GFG username
        
    Returns:
        Formatted GFG stats dictionary
    """
    try:
        if not username or username.strip() == "":
            return {"error": "Username is required"}
        
        logger.info(f"Fetching GFG stats for {username}")
        
        # Use synchronous requests
        import json
        import re
        from bs4 import BeautifulSoup
        
        GFG_SUBMISSION_API = "https://practiceapi.geeksforgeeks.org/api/v1/user/problems/submissions/"
        GFG_PROFILE_PAGE = "https://www.geeksforgeeks.org/user/{username}/"
        
        # Step 1: Fetch API data
        payload = {
            "handle": username,
            "requestType": "",
            "year": "",
            "month": ""
        }
        
        api_res = httpx.post(GFG_SUBMISSION_API, json=payload, headers=HEADERS, timeout=20)
        
        if api_res.status_code != 200:
            return {
                "error": f"API error: status {api_res.status_code}"
            }
        
        # Parse API response
        try:
            api_data_json = json.loads(api_res.text)
            result = api_data_json.get("result", {})
            
            basic = len(result.get("Basic", {}))
            easy = len(result.get("Easy", {}))
            medium = len(result.get("Medium", {}))
            hard = len(result.get("Hard", {}))
            
            api_data = {
                "basic": basic,
                "easy": easy,
                "medium": medium,
                "hard": hard,
                "total": basic + easy + medium + hard,
            }
        except Exception as e:
            logger.error(f"Error parsing API response: {e}")
            return {"error": str(e)}
        
        # Step 2: Fetch profile page
        url = GFG_PROFILE_PAGE.format(username=username)
        profile_res = httpx.get(url, headers=HEADERS, timeout=20)
        
        profile_data = {}
        if profile_res.status_code == 200:
            try:
                soup = BeautifulSoup(profile_res.text, 'lxml')
                
                # Extract Full Name
                name_elem = soup.find('h2', class_='NewProfile_name__N_Nlw')
                if name_elem:
                    profile_data['fullName'] = name_elem.get_text(strip=True)
                
                # Extract Profile Picture URL
                img_elem = soup.find('img', class_=re.compile(r'rounded-full', re.I))
                if img_elem and img_elem.get('src'):
                    src = img_elem['src']
                    if src.startswith('http'):
                        profile_data['profilePicture'] = src
                    elif src.startswith('/'):
                        profile_data['profilePicture'] = 'https://www.geeksforgeeks.org' + src
                    else:
                        profile_data['profilePicture'] = 'https://www.geeksforgeeks.org/' + src
                
                # Extract Institute Name
                qualifications = soup.find('div', class_=re.compile(r'[Qq]ualification', re.I))
                if qualifications:
                    p_tag = qualifications.find('p')
                    if p_tag:
                        institute_text = p_tag.get_text(strip=True)
                        if institute_text and len(institute_text) < 100:
                            profile_data['institute'] = institute_text
                
                # Extract Coding Score
                score_elements = soup.find_all(class_="ScoreContainer_value__7yy7h")
                if len(score_elements) > 0:
                    score_text = score_elements[0].get_text(strip=True)
                    score_match = re.search(r'(\d+)', score_text)
                    if score_match:
                        profile_data['codingScore'] = int(score_match.group(1))
                
                # Extract Institute Rank
                if len(score_elements) > 2:
                    rank_text = score_elements[2].get_text(strip=True)
                    rank_match = re.search(r'(\d+)', rank_text)
                    if rank_match:
                        profile_data['instituteRank'] = int(rank_match.group(1))
                
                # Extract Max Streak
                streak_values = soup.find_all(class_="PotdContainer_statValue__nt1dr")
                if len(streak_values) > 0:
                    max_streak_text = streak_values[0].get_text(strip=True)
                    max_streak_match = re.search(r'(\d+)', max_streak_text)
                    if max_streak_match:
                        profile_data['maxStreak'] = int(max_streak_match.group(1))
                
                # Extract Current POTD Streak
                potd_text_elem = soup.find(string=re.compile(r'\d+\s*Day\s*POTD\s*Streak', re.I))
                if potd_text_elem:
                    potd_text = potd_text_elem.get_text(strip=True)
                    potd_match = re.search(r'(\d+)\s*Day', potd_text, re.I)
                    if potd_match:
                        profile_data['currentStreak'] = int(potd_match.group(1))
            except Exception as e:
                logger.debug(f"Error scraping profile page: {e}")
        
        # Combine all data
        complete_data = {
            "user": username,
            **api_data,
            **profile_data
        }
        
        # Format the response
        formatted_result = format_gfg_response(complete_data)
        return formatted_result
    
    except Exception as e:
        logger.error(f"Error fetching GFG stats for {username}: {e}")
        return {"error": str(e)}


# ======================================================
# API ENDPOINTS
# ======================================================

@app.get("/")
async def health_check():
    """Health check endpoint for monitoring"""
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "service": "GFG Scraper API",
        "version": "1.0.0"
    }


@app.get("/gfg")
async def scrape_user(username: str):
    """Scrape a single user by username using BeautifulSoup for both API and UI
    
    Usage: /gfg?username=yuvasrisai18
    """
    try:
        logger.info(f"Scraping user: {username}")
        if not username or username.strip() == "":
            raise HTTPException(status_code=400, detail="Username parameter is required")

        sem = asyncio.Semaphore(1)
        
        try:
            async with httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                limits=httpx.Limits(max_connections=10),
                timeout=30
            ) as client:
                logger.info(f"Fetching data for {username}...")
                result = await fetch_user_complete(client, username, sem)
            
            # Check if there was an error
            if "error" in result:
                logger.error(f"Error for user {username}: {result['error']}")
            else:
                logger.info(f"Successfully scraped user {username}")
            
            # Format the response
            formatted_result = format_gfg_response(result)
            return formatted_result
        
        except Exception as e:
            logger.error(f"Exception in scrape_user: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


