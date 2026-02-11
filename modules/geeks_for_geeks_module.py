
import asyncio
import sys
import httpx
from fastapi import FastAPI, HTTPException

# Fix for Windows asyncio subprocess issues with Playwright
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from config import (
    fetch_user_complete,
    create_browser,
    HEADERS
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
# API ENDPOINTS
# ======================================================

@app.get("/")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": "GFG Scraper API",
        "version": "1.0.0"
    }


@app.get("/gfg")
async def scrape_user(username: str):
    """Scrape a single user by username - returns JSON
    
    Usage: /gfg?username=yuvasrisai18
    """
    try:
        if not username or username.strip() == "":
            raise HTTPException(status_code=400, detail="Username parameter is required")

        # Create browser for single user
        browser, playwright_instance = await create_browser()
        
        try:
            sem = asyncio.Semaphore(1)
            page = await browser.new_page()
            
            try:
                async with httpx.AsyncClient(
                    headers=HEADERS,
                    follow_redirects=True,
                    limits=httpx.Limits(max_connections=10)
                ) as client:
                    result = await fetch_user_complete(client, username, sem, page)
                
                # Format the response
                formatted_result = format_gfg_response(result)
                return formatted_result
            finally:
                await page.close()
        finally:
            # Close browser
            await browser.close()
            await playwright_instance.stop()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

