
import asyncio
import logging
import httpx
from fastapi import FastAPI, HTTPException

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from config import (
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


