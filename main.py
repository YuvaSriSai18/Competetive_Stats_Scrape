from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from modules.codechef_module import get_codechef_profile
from modules.geeks_for_geeks_module import get_gfg_stats
from modules.github_module import get_github_profile
from modules.leetcode_module import get_leetcode_full_profile
import os
import uvicorn
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Any, List
import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.firestore import DELETE_FIELD
import json
import time

load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
db = None
try:
    firebase_admin.get_app()
    db = firestore.client()
except ValueError:
    # App not initialized yet
    firebase_creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")
    if not firebase_creds_json:
        logger.warning("⚠️ FIREBASE_CREDENTIALS_JSON not set. Firebase will not be available. Set it for production.")
    else:
        try:
            # Parse the JSON string into a dictionary
            creds_dict = json.loads(firebase_creds_json)
            # Initialize Firebase with the parsed credentials
            creds = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(creds)
            db = firestore.client()
            logger.info("✓ Firebase Admin SDK initialized successfully")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in FIREBASE_CREDENTIALS_JSON: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firebase: {str(e)}")
except Exception as e:
    logger.warning(f"⚠️ Error initializing Firebase: {str(e)}")

# Load secret key for API security
SCRAPING_SECRET_KEY = os.environ.get("SCRAPING_SECRET_KEY", "")
if not SCRAPING_SECRET_KEY:
    logger.warning("⚠️ SCRAPING_SECRET_KEY not set. Set it in .env for production security.")

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_secret_header(x_secret_key: str = Header(...)):
    """
    Verify the secret key header for secure endpoint access.
    
    Args:
        x_secret_key: Secret key provided in X-Secret-Key header
        
    Raises:
        HTTPException: If secret key is missing or invalid
    """
    if not SCRAPING_SECRET_KEY:
        logger.warning("⚠️ Scraping endpoint called but SCRAPING_SECRET_KEY not configured")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: SCRAPING_SECRET_KEY not set"
        )
    
    if x_secret_key != SCRAPING_SECRET_KEY:
        logger.error(f"🚫 Unauthorized scraping attempt with invalid secret key")
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing secret key"
        )
    
    return x_secret_key


@app.get("/")
def home():
    return {"message": "✅ API is running. Use /leetcode, /codechef, /gfg, /github."}


# ============================================================================
# FIRESTORE BATCH SCRAPING ENDPOINT
# ============================================================================

def create_scraping_tasks() -> List[Dict[str, Any]]:
    """
    Create scraping tasks from all coding_stats documents across all institutions.
    Uses Firestore collectionGroup query to fetch all documents efficiently.
    
    Returns:
        List of task dictionaries containing: institutionId, docId, platform, username
    """
    if db is None:
        raise RuntimeError("Firestore database not initialized. Cannot create scraping tasks.")
    
    tasks = []
    try:
        # Use collectionGroup query to fetch all coding_stats across all institutions
        docs = db.collection_group("coding_stats").stream()
        
        for doc in docs:
            task = {
                "institutionId": doc.get("institutionId"),
                "docId": doc.id,
                "platform": doc.get("platform"),
                "username": doc.get("username"),
                "firestoreRef": doc.reference
            }
            tasks.append(task)
        
        logger.info(f"Created {len(tasks)} scraping tasks from Firestore")
        return tasks
    
    except Exception as e:
        logger.error(f"Error creating scraping tasks: {str(e)}")
        raise


def flatten_codechef_data(scraper_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten CodeChef scraper output from nested structure to root level.
    
    Transforms:
        {"codechef": {"badge_count": 2, "calendar": {...}, ...}}
    Into:
        {"badge_count": 2, "calendar": {...}, ...}
    
    Args:
        scraper_output: Raw output from get_codechef_profile()
        
    Returns:
        Flattened dictionary ready for Firestore storage
    """
    if not scraper_output or not isinstance(scraper_output, dict):
        return {}
    
    # Extract the nested codechef data
    codechef_data = scraper_output.get("codechef", {})
    
    # Check for errors in the response
    if "error" in codechef_data:
        raise ValueError(f"CodeChef scraping error: {codechef_data['error']}")
    
    # Return flattened data (all fields at root level)
    return codechef_data


def flatten_github_data(scraper_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten GitHub scraper output from nested structure to root level.
    
    Transforms:
        {"github": {"public_repos": 15, "calendar": {...}, ...}}
    Into:
        {"public_repos": 15, "calendar": {...}, ...}
    
    Args:
        scraper_output: Raw output from get_github_profile()
        
    Returns:
        Flattened dictionary ready for Firestore storage
    """
    if not scraper_output or not isinstance(scraper_output, dict):
        return {}
    
    # Extract the nested github data
    github_data = scraper_output.get("github", {})
    
    # Check for errors in the response
    if "error" in github_data:
        raise ValueError(f"GitHub scraping error: {github_data['error']}")
    
    # Return flattened data (all fields at root level)
    return github_data


def flatten_leetcode_data(scraper_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten LeetCode scraper output from nested structure to root level.
    
    Transforms:
        {"calendar": {...}, "profile": {"username": "...", ...}}
    Into:
        {"calendar": {...}, "profile": {"username": "...", ...}}
    (LeetCode already uses root-level structure, just pass through)
    
    Args:
        scraper_output: Raw output from get_leetcode_full_profile()
        
    Returns:
        Flattened dictionary ready for Firestore storage
    """
    if not scraper_output or not isinstance(scraper_output, dict):
        return {}
    
    # Check for errors in the response
    if "error" in scraper_output:
        raise ValueError(f"LeetCode scraping error: {scraper_output['error']}")
    
    # LeetCode output is already at root level, return as-is
    return scraper_output


def flatten_gfg_data(scraper_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten GeeksforGeeks scraper output from nested structure to root level.
    
    Args:
        scraper_output: Raw output from get_gfg_stats()
        
    Returns:
        Flattened dictionary ready for Firestore storage
    """
    if not scraper_output or not isinstance(scraper_output, dict):
        return {}
    
    # Check for errors in the response
    if "error" in scraper_output:
        raise ValueError(f"GeeksforGeeks scraping error: {scraper_output['error']}")
    
    # GFG output is already at root level, return as-is
    return scraper_output

def prepare_firestore_update(
    platform: str,
    scraped_data: Dict[str, Any],
    institution_id: str
) -> Dict[str, Any]:
    """
    Transform scraper output into Firestore document update format.
    Flattens all platform data and preserves metadata fields.
    
    Args:
        platform: Platform name ("leetcode", "github", "codechef", "gfg")
        scraped_data: Raw output from scraper function
        institution_id: Institution ID for reference
        
    Returns:
        Dictionary formatted for Firestore set/update with merge=True
    """
    # Metadata fields that should always be at root level
    update_data = {
        "lastUpdated": datetime.utcnow(),
        "scrapingStatus": "success"
    }
    
    # Process scraped data based on platform - flatten all platforms
    if platform == "codechef":
        flattened_data = flatten_codechef_data(scraped_data)
        update_data.update(flattened_data)
    elif platform == "github":
        flattened_data = flatten_github_data(scraped_data)
        update_data.update(flattened_data)
    elif platform == "leetcode":
        flattened_data = flatten_leetcode_data(scraped_data)
        update_data.update(flattened_data)
    elif platform == "gfg":
        flattened_data = flatten_gfg_data(scraped_data)
        update_data.update(flattened_data)
    else:
        raise ValueError(f"Unknown platform: {platform}")
    
    return update_data

def scrape_worker(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Worker function to scrape data for a single platform and update Firestore.
    Calls the appropriate scraper based on platform type.
    
    Args:
        task: Dictionary with institutionId, docId, platform, username, firestoreRef
        
    Returns:
        Dictionary with task status and results
    """
    platform = task.get("platform")
    username = task.get("username")
    institution_id = task.get("institutionId")
    firestore_ref = task.get("firestoreRef")
    
    result = {
        "institutionId": institution_id,
        "docId": task.get("docId"),
        "platform": platform,
        "username": username,
        "success": False,
        "data": None,
        "error": None,
        "skipped": False
    }
    
    try:
        scraped_data = None
        
        # Route to correct scraper function based on platform
        if platform == "leetcode":
            scraped_data = get_leetcode_full_profile(username)
        elif platform == "github":
            scraped_data = get_github_profile(username)
        elif platform == "codechef":
            scraped_data = get_codechef_profile(username)
        elif platform == "gfg":
            scraped_data = get_gfg_stats(username)
        else:
            raise ValueError(f"Unknown platform: {platform}")
        
        # Prepare update data with proper structure for this platform
        update_data = prepare_firestore_update(platform, scraped_data, institution_id)
        
        # Add successful status and remove any previous error field
        update_data["scrapingStatus"] = "success"
        update_data["lastScrapingError"] = DELETE_FIELD
        
        # Use set() with merge=True to preserve existing metadata fields
        firestore_ref.set(update_data, merge=True)
        
        result["success"] = True
        result["data"] = scraped_data
        
        logger.info(
            f"✓ Platform: {platform} | Username: {username} | "
            f"Institution: {institution_id} | Status: Success"
        )
    
    except Exception as e:
        error_msg = str(e)
        result["error"] = error_msg
        
        # Update Firestore with error status (preserves metadata with merge=True)
        try:
            error_update = {
                "scrapingStatus": "failed",
                "lastScrapingError": error_msg,
                "lastUpdated": datetime.utcnow()
            }
            firestore_ref.set(error_update, merge=True)
        except Exception as update_error:
            logger.error(f"Failed to update error status in Firestore: {str(update_error)}")
        
        logger.error(
            f"✗ Platform: {platform} | Username: {username} | "
            f"Institution: {institution_id} | Error: {error_msg}"
        )
    
    return result

def process_scraping_tasks_concurrent(
    tasks: List[Dict[str, Any]], 
    max_workers: int = 5
) -> Dict[str, Any]:
    """
    Process scraping tasks concurrently using ThreadPoolExecutor.
    Includes rate-limiting: sleep 1.5 minutes after every 5 completed tasks.
    
    Args:
        tasks: List of scraping tasks
        max_workers: Maximum number of concurrent worker threads (default: 5)
        
    Returns:
        Dictionary with summary statistics and results
    """
    results = []
    successful = 0
    failed = 0
    skipped = 0
    completed_count = 0  # Counter for rate-limiting
    
    logger.info(f"Starting concurrent processing with {max_workers} workers for {len(tasks)} tasks")
    
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(scrape_worker, task): task for task in tasks}
            
            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result.get("skipped"):
                        skipped += 1
                    elif result["success"]:
                        successful += 1
                    else:
                        failed += 1
                    
                    completed_count += 1
                    
                    # Rate-limiting: sleep after every 5 completed tasks
                    if completed_count % 5 == 0:
                        logger.info(f"Completed {completed_count} tasks. Pausing for 1.5 minutes to avoid rate limiting...")
                        time.sleep(90)  # 1.5 minutes
                        logger.info(f"Resuming after rate-limit pause. Continuing with remaining tasks...")
                
                except Exception as e:
                    logger.error(f"Worker thread error: {str(e)}")
                    failed += 1
                    completed_count += 1
                    
                    # Rate-limiting: sleep after every 5 completed tasks (including failed ones)
                    if completed_count % 5 == 0:
                        logger.info(f"Completed {completed_count} tasks. Pausing for 1.5 minutes to avoid rate limiting...")
                        time.sleep(90)  # 1.5 minutes
                        logger.info(f"Resuming after rate-limit pause. Continuing with remaining tasks...")
    
    except Exception as e:
        logger.error(f"Error during concurrent processing: {str(e)}")
        raise
    
    # Summary
    summary = {
        "total_tasks": len(tasks),
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    logger.info(
        f"Batch scraping completed: {successful} successful, {failed} failed, {skipped} skipped out of {len(tasks)} tasks"
    )
    
    return summary

@app.get("/scrape-coding-stats")
def scrape_coding_stats(x_secret_key: str = Header(..., description="Secret key for endpoint security")):
    """
    Scrape coding statistics for all users across all institutions.
    Uses Firestore collectionGroup query to fetch all coding_stats documents
    and processes them concurrently.
    
    Headers Required:
        X-Secret-Key: Must match SCRAPING_SECRET_KEY environment variable
    
    Returns:
        Dictionary with batch processing results and statistics
    """
    # Verify secret key header
    verify_secret_header(x_secret_key)
    
    # Check if Firebase is initialized
    if db is None:
        return {
            "status": "error",
            "message": "Firebase not initialized. Set FIREBASE_CREDENTIALS_JSON environment variable.",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    try:
        logger.info("Starting batch scraping operation from /scrape-coding-stats endpoint")
        
        # Step 1: Create tasks from Firestore collectionGroup query
        tasks = create_scraping_tasks()
        
        if not tasks:
            logger.warning("No scraping tasks found in Firestore")
            return {
                "status": "no_tasks",
                "message": "No coding_stats documents found",
                "total_tasks": 0
            }
        
        # Step 2: Process tasks concurrently
        summary = process_scraping_tasks_concurrent(tasks, max_workers=5)
        
        # Step 3: Return results
        return {
            "status": "completed",
            "message": "Batch scraping completed successfully",
            **summary
        }
    
    except Exception as e:
        error_msg = f"Batch scraping failed: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg,
            "timestamp": datetime.utcnow().isoformat()
        }

# --- LeetCode API ---
@app.get("/leetcode")
def leetcode_stats(username: str = Query(..., description="LeetCode username")):
    try:
        stats = get_leetcode_full_profile(username)
        return stats
    except Exception as e:
        return {"error": str(e)}

# --- CodeChef API ---
@app.get("/codechef")
def codechef_stats(username: str = Query(..., description="CodeChef username")):
    result = get_codechef_profile(username)
    
    if "error" in result.get("codechef", {}):
        return {"error": result["codechef"]["error"]}

    data = result.get("codechef", {})

    return {
        "calendar": data.get("calendar", {}),
        "profile": {
            "stars": data.get("stars", 0),
            "rating": data.get("rating", None),
            "max_rating": data.get("max_rating", None),
            "problems_solved": data.get("problems_solved", 0),
            "contests_participated": data.get("contests_participated", 0),
            "badge_count": data.get("badge_count", 0),
            "contest_count": data.get("contest_count", 0)
        },
        "badge_details": data.get("badge_details", []),
        "contest_history": data.get("contest_history", []),
        "participated_contests": data.get("participated_contests", [])
    }


# --- GeeksforGeeks API ---
@app.get("/gfg")
def gfg_stats(username: str = Query(..., description="GeeksForGeeks username")):
    try:
        stats = get_gfg_stats(username)
        return stats
    except Exception as e:
        return {"error": str(e)}

# --- GitHub API ---
@app.get("/github")
def github_stats(username: str = Query(..., description="GitHub username")):
    result = get_github_profile(username)
    return result

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))   # Render assigns PORT automatically
    uvicorn.run("main:app", host="0.0.0.0", port=port)