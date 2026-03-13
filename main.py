from fastapi import FastAPI, Query
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

load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
try:
    firebase_admin.get_app()
except ValueError:
    # App not initialized yet
    creds = credentials.Certificate(os.environ.get("FIREBASE_CREDENTIALS_PATH", "credentials.json"))
    firebase_admin.initialize_app(creds)

db = firestore.client()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    Skips scraping if less than 24 hours have passed since lastUpdated.
    
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
        # Check if 24 hours have passed since lastUpdated
        doc_data = firestore_ref.get().to_dict()
        last_updated = doc_data.get("lastUpdated")
        
        if last_updated:
            # Handle both datetime objects and timestamps
            if hasattr(last_updated, 'timestamp'):
                # It's a datetime object
                last_updated_time = last_updated
            else:
                # It's already a python datetime
                last_updated_time = last_updated
            
            current_time = datetime.utcnow()
            time_diff = current_time - last_updated_time
            
            # Check if less than 24 hours have passed
            if time_diff.total_seconds() < 86400:  # 86400 seconds = 24 hours
                result["skipped"] = True
                logger.info(
                    f"⊘ Platform: {platform} | Username: {username} | "
                    f"Institution: {institution_id} | Status: Skipped (last updated {time_diff.total_seconds() / 3600:.1f}h ago)"
                )
                return result
        
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
                
                except Exception as e:
                    logger.error(f"Worker thread error: {str(e)}")
                    failed += 1
    
    except Exception as e:
        logger.error(f"Error during concurrent processing: {str(e)}")
        raise
    
    # Summary
    summary = {
        "total_tasks": len(tasks),
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
        "timestamp": datetime.utcnow().isoformat(),
        # "results": results
    }
    
    logger.info(
        f"Batch scraping completed: {successful} successful, {failed} failed, {skipped} skipped out of {len(tasks)} tasks"
    )
    
    return summary


@app.post("/scrape-coding-stats")
def scrape_coding_stats():
    """
    Scrape coding statistics for all users across all institutions.
    Uses Firestore collectionGroup query to fetch all coding_stats documents
    and processes them concurrently.
    
    Returns:
        Dictionary with batch processing results and statistics
    """
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
    port = int(os.environ.get("PORT", 10000))   # Render assigns PORT automatically
    uvicorn.run("main:app", host="0.0.0.0", port=port)
# load_dotenv()

# print_lock = threading.Lock()  # Thread-safe printing

# @app.route("/")
# def home():
#     return "✅ API is running. Use `/stats` (POST) with JSON data."

# @app.route("/stats", methods=["POST"])
# def batch_stats():
#     data = request.json.get("data", [])
#     results = [{} for _ in range(len(data))]

#     def process_row(index, entry):
#         try:
#             lc = entry.get("leetcode(username)")
#             cc = entry.get("codechef(username)")
#             gfg = entry.get("geeksforgeeks(username)")
#             gh = entry.get("github(username)")

#             row_stats = {}

#             if lc:
#                 try:
#                     lc_data = get_leetcode_full_profile(lc)
#                     row_stats["leetcode"] = lc_data  # Full structure: calendar + profile

#                 except Exception as e:
#                     row_stats["LC Error"] = str(e)

#             if gfg:
#                 try:
#                     gfg_data = get_gfg_stats(gfg)
#                     solved = gfg_data.get("solvedStats", {})
#                     row_stats["GFG Basic"] = solved.get("basic", {}).get("count", 0)
#                     row_stats["GFG Easy"] = solved.get("easy", {}).get("count", 0)
#                     row_stats["GFG Medium"] = solved.get("medium", {}).get("count", 0)
#                     row_stats["GFG Hard"] = solved.get("hard", {}).get("count", 0)
#                 except Exception as e:
#                     row_stats["GFG Error"] = str(e)

#             if cc:
#                 try:
#                     cc_data = get_codechef_stars(cc)
#                     row_stats["CC Stars"] = cc_data.get("codechef", {}).get("stars", 0)
#                 except Exception as e:
#                     row_stats["CC Error"] = str(e)

#             if gh:
#                 try:
#                     gh_data = get_github_profile(gh)
#                     row_stats["GitHub Repos"] = gh_data.get("github", {}).get("public_repos", 0)
#                 except Exception as e:
#                     row_stats["GH Error"] = str(e)

#             results[index] = row_stats

#             with print_lock:
#                 print(f"[✓] Row {index + 1} processed: {row_stats}")

#         except Exception as err:
#             with print_lock:
#                 print(f"[X] Error processing row {index + 1}: {err}")
#             results[index] = {"error": str(err)}

#     threads = []
#     for i, row in enumerate(data):
#         t = threading.Thread(target=process_row, args=(i, row))
#         threads.append(t)
#         t.start()
#         time.sleep(30)  # Delay between thread starts to avoid rate limits

#     # Wait for all threads to complete
#     for t in threads:
#         t.join()

#     return jsonify(results)

# @app.route("/user/stats", methods=["GET", "POST"])
# def stats():
#     if request.method == "POST":
#         data = request.json.get("data", [])
#         results = [{} for _ in range(len(data))]

#         def process_row(index, entry):
#             try:
#                 lc = entry.get("leetcode")
#                 cc = entry.get("codechef")
#                 gfg = entry.get("geeksforgeeks")
#                 gh = entry.get("github")

#                 row_stats = {}

#                 if lc:
#                     try:
#                         lc_data = get_leetcode_full_profile(lc)
#                         row_stats["leetcode"] = lc_data  # Full structure: calendar + profile

#                     except Exception as e:
#                         row_stats["LC Error"] = str(e)

#                 if gfg:
#                     try:
#                         gfg_data = get_gfg_stats(gfg)
#                         solved = gfg_data.get("solvedStats", {})
#                         row_stats["GFG Basic"] = solved.get("basic", {}).get("count", 0)
#                         row_stats["GFG Easy"] = solved.get("easy", {}).get("count", 0)
#                         row_stats["GFG Medium"] = solved.get("medium", {}).get("count", 0)
#                         row_stats["GFG Hard"] = solved.get("hard", {}).get("count", 0)
#                     except Exception as e:
#                         row_stats["GFG Error"] = str(e)

#                 if cc:
#                     try:
#                         cc_data = get_codechef_stars(cc)
#                         row_stats["CC Stars"] = cc_data.get("codechef", {}).get("stars", 0)
#                     except Exception as e:
#                         row_stats["CC Error"] = str(e)

#                 if gh:
#                     try:
#                         gh_data = get_github_profile(gh)
#                         row_stats["GitHub Repos"] = gh_data.get("github", {}).get("public_repos", 0)
#                     except Exception as e:
#                         row_stats["GH Error"] = str(e)

#                 results[index] = row_stats

#                 with print_lock:
#                     print(f"[✓] Row {index + 1} processed: {row_stats}")

#             except Exception as err:
#                 with print_lock:
#                     print(f"[X] Error processing row {index + 1}: {err}")
#                 results[index] = {"error": str(err)}

#         threads = []
#         for i, row in enumerate(data):
#             t = threading.Thread(target=process_row, args=(i, row))
#             threads.append(t)
#             t.start()
#             time.sleep(30)  # Delay to avoid rate limits

#         for t in threads:
#             t.join()

#         return jsonify(results)

#     elif request.method == "GET":
#         gfg_username = request.args.get("gfg")
#         leetcode_username = request.args.get("lc")  
#         codechef_username = request.args.get("cc")
#         github_username = request.args.get("gh")

#         result = {}

#         try:
#             if gfg_username:
#                 gfg_data = get_gfg_stats(gfg_username)
#                 result["geeksforgeeks"] = gfg_data if "error" not in gfg_data else {"error": gfg_data["error"]}
#             else:
#                 result["geeksforgeeks"] = {"error": "No GFG username provided"}
#         except Exception as e:
#             result["geeksforgeeks"] = {"error": str(e)}

#         try:
#             if leetcode_username:
#                 lc_data = get_leetcode_full_profile(leetcode_username)
#                 result["leetcode"] = lc_data

#             else:
#                 result["leetcode"] = {"error": "No LeetCode username provided"}
#         except Exception as e:
#             result["leetcode"] = {"error": str(e)}

#         try:
#             if codechef_username:
#                 cc_data = get_codechef_stars(codechef_username)
#                 result["codechef"] = cc_data.get("codechef", {"error": "Failed to parse CodeChef data"})
#             else:
#                 result["codechef"] = {"error": "No CodeChef username provided"}
#         except Exception as e:
#             result["codechef"] = {"error": str(e)}

#         try:
#             if github_username:
#                 gh_data = get_github_profile(github_username)
#                 result["github"] = gh_data.get("github", {"error": "Failed to parse GitHub data"})
#             else:
#                 result["github"] = {"error": "No GitHub username provided"}
#         except Exception as e:
#             result["github"] = {"error": str(e)}

#         return jsonify(result)

# if __name__ == "__main__":
#     port = int(os.environ.get("PORT", 5001))
#     app.run(host="0.0.0.0", port=port)

# # from flask import Flask, request, jsonify
# # from flask_cors import CORS
# # from modules.codechef_module import get_codechef_stars
# # from modules.geeks_for_geeks_module import get_gfg_stats
# # from modules.github_module import get_github_profile
# # from modules.leetcode_module import get_leetcode_solved

# # app = Flask(__name__)
# # CORS(app, resources={r"/*": {"origins": "*"}})

# # @app.route("/")
# # def home():
# #     return "✅ API is running. Use `/stats` with query params."

# # # No need to include app.run() here; Gunicorn handles it in production
# # if __name__ == "__main__":
# #     from dotenv import load_dotenv
# #     load_dotenv()

# #     import os
# #     port = int(os.environ.get("PORT", 5001))
# #     app.run(host="0.0.0.0", port=port)
