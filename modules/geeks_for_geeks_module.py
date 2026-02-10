# import requests
# import json
# from bs4 import BeautifulSoup as bs

# def get_gfg_stats(username):
#     PRACTICE_URL = f'https://auth.geeksforgeeks.org/user/{username}/practice/'
#     PROFILE_URL = f'https://www.geeksforgeeks.org/user/{username}/'

#     headers = {
#         "User-Agent": "Mozilla/5.0"
#     }

#     # 1. Get practice page for problem stats
#     profilePage = requests.get(PRACTICE_URL, headers=headers)
#     if profilePage.status_code != 200:
#         return {"error": "Practice profile not found"}

#     soup = bs(profilePage.content, 'html.parser')

#     script_tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
#     if not script_tag:
#         return {"error": "Could not find user data script"}

#     try:
#         user_data = json.loads(script_tag.string)
#         user_info = user_data["props"]["pageProps"]["userInfo"]
#         user_submissions = user_data["props"]["pageProps"]["userSubmissionsInfo"]
#     except (KeyError, json.JSONDecodeError):
#         return {"error": "Failed to parse user data"}

#     generalInfo = {
#         "userName": username,
#         "fullName": user_info.get("name", ""),
#         "profilePicture": user_info.get("profile_image_url", ""),
#         "institute": user_info.get("institute_name", ""),
#         "instituteRank": user_info.get("institute_rank", ""),
#         "currentStreak": user_info.get("pod_solved_longest_streak", "00"),
#         "maxStreak": user_info.get("pod_solved_global_longest_streak", "00"),
#         "codingScore": user_info.get("score", 0),
#         "monthlyScore": user_info.get("monthly_score", 0),
#         "totalProblemsSolved": user_info.get("total_problems_solved", 0),
#         "contestRating": None  # placeholder
#     }

#     solvedStats = {}
#     for difficulty, problems in user_submissions.items():
#         solvedStats[difficulty.lower()] = {
#             "count": len(problems)
#         }

#     # 2. Get profile page for contest rating
#     profilePage2 = requests.get(PROFILE_URL, headers=headers)
#     if profilePage2.status_code == 200:
#         soup2 = bs(profilePage2.content, 'html.parser')
#         try:
#             rating_element = soup2.find('div', string='Contest Rating')
#             if rating_element:
#                 rating_value = rating_element.find_next('div')
#                 if rating_value:
#                     generalInfo["contestRating"] = int(rating_value.text.strip())
#         except Exception as e:
#             generalInfo["contestRating"] = None

#     return {
#         "info": generalInfo,
#         "solvedStats": solvedStats
#     }


# # Example direct call to test the module
# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) > 1:
#         username = sys.argv[1]
#     else:
#         username = input("Enter GFG username: ")

#     data = get_gfg_stats(username)

#     if "error" in data:
#         print("❌", data["error"])
#     else:
#         print(json.dumps(data, indent=4))


import asyncio
from typing import List
import httpx
from fastapi import FastAPI, HTTPException

from utils.config import (
    fetch_user_complete,
    create_webdriver,
    HEADERS,
    MAX_CONCURRENT_REQUESTS,
    BATCH_SIZE
)

app = FastAPI(title="GFG Scraper API", version="1.0.0")


# ======================================================
# FORMAT RESPONSE FUNCTION
# ======================================================

def format_gfg_response(raw_data: dict) -> dict:
    """Format raw GFG data into the required JSON structure"""
    
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
        "monthlyScore": raw_data.get("monthlyScore", 0),
        "contestRating": raw_data.get("contestRating", None)
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
# SYNCHRONOUS WRAPPER FUNCTION FOR MAIN.PY
# ======================================================

def get_gfg_stats(username: str):
    """Synchronous wrapper function to fetch GFG stats - for backward compatibility with main.py"""
    try:
        # Create driver
        driver = create_webdriver()
        
        try:
            sem = asyncio.Semaphore(1)
            
            # Run async function in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def fetch():
                async with httpx.AsyncClient(
                    headers=HEADERS,
                    follow_redirects=True,
                    limits=httpx.Limits(max_connections=10)
                ) as client:
                    result = await fetch_user_complete(client, username, sem, driver)
                    return result
            
            result = loop.run_until_complete(fetch())
            loop.close()
            
            # Format the response
            formatted_result = format_gfg_response(result)
            
            return formatted_result
        finally:
            # Close driver
            driver.quit()
    
    except Exception as e:
        return {
            "info": {},
            "solvedStats": {},
            "error": str(e)
        }


# ======================================================
# BATCH PROCESSING FUNCTION
# ======================================================

async def batch_fetch(users: List[str], driver):
    """Fetch data for all users in batches with shared WebDriver"""
    sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    all_results = []

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        limits=httpx.Limits(max_connections=10)
    ) as client:

        # Process users in batches
        total_batches = (len(users) + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"\n[START] Running scraper for {len(users)} users in {total_batches} batches...\n")
        
        for i in range(0, len(users), BATCH_SIZE):
            batch = users[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            
            print(f"[Batch {batch_num}/{total_batches}] Processing {len(batch)} users...")
            
            # Pass driver to fetch_user_complete
            tasks = [fetch_user_complete(client, u, sem, driver) for u in batch]
            batch_results = await asyncio.gather(*tasks)
            
            # Format each result
            formatted_results = [format_gfg_response(r) for r in batch_results]
            all_results.extend(formatted_results)
        
        print("\n[COMPLETE] Scraping finished!\n")

    return all_results





@app.get("/")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": "GFG Scraper API",
        "version": "1.0.0"
    }


@app.get("/scrape")
async def scrape_users(usernames: str):
    """Scrape multiple users via query parameter
    
    Usage: /scrape?usernames=user1,user2,user3
    """
    try:
        if not usernames or usernames.strip() == "":
            raise HTTPException(status_code=400, detail="usernames parameter is required")

        # Split comma-separated usernames
        users = [u.strip() for u in usernames.split(",") if u.strip()]
        
        if not users:
            raise HTTPException(status_code=400, detail="No valid usernames provided")

        # Create ONE driver for all users
        driver = create_webdriver()
        
        try:
            results = await batch_fetch(users, driver)
            
            success_count = sum(1 for r in results if 'error' not in r)
            error_count = len(results) - success_count
            
            return {
                "status": "success",
                "total_users": len(users),
                "successful": success_count,
                "errors": error_count,
                "results": results
            }
        finally:
            # Close driver
            driver.quit()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/gfg")
async def scrape_user(username: str):
    """Scrape a single user by username - returns JSON
    
    Usage: /gfg?username=yuvasrisai18
    """
    try:
        if not username or username.strip() == "":
            raise HTTPException(status_code=400, detail="Username parameter is required")

        # Create driver for single user
        driver = create_webdriver()
        
        try:
            sem = asyncio.Semaphore(1)
            
            async with httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                limits=httpx.Limits(max_connections=10)
            ) as client:
                result = await fetch_user_complete(client, username, sem, driver)
            
            # Format the response
            formatted_result = format_gfg_response(result)
            return formatted_result
        finally:
            # Close driver
            driver.quit()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
