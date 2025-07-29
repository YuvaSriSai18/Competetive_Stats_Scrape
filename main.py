from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from modules.codechef_module import get_codechef_profile
from modules.geeks_for_geeks_module import get_gfg_stats
from modules.github_module import get_github_profile
from modules.leetcode_module import get_leetcode_full_profile
import os

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route("/")
def home():
    return "✅ API is running. Use /leetcode, /codechef, /gfg, /github."

# --- LeetCode API ---
@app.route("/leetcode", methods=["GET"])
def leetcode_stats():
    username = request.args.get("username")
    if not username:
        return jsonify({"error": "Missing LeetCode username"}), 400
    try:
        stats = get_leetcode_full_profile(username)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- CodeChef API ---
@app.route("/codechef", methods=["GET"])
def codechef_stats():
    username = request.args.get("username")
    if not username:
        return jsonify({"error": "Missing username"}), 400

    result = get_codechef_profile(username)
    
    if "error" in result.get("codechef", {}):
        return jsonify({"error": result["codechef"]["error"]}), 500

    data = result.get("codechef", {})

    return jsonify({
        "calendar": data.get("calendar", {}),
        "profile": {
            "stars": data.get("stars", 0),
            "rating": data.get("rating", None),
            "max_rating": data.get("max_rating", None),
            "problems_solved": data.get("problems_solved", 0),
            "contests_participated": data.get("contests_participated", 0)
        }
    }), 200


# --- GeeksforGeeks API ---
@app.route("/gfg", methods=["GET"])
def gfg_stats():
    username = request.args.get("username")
    if not username:
        return jsonify({"error": "Missing GFG username"}), 400
    try:
        stats = get_gfg_stats(username)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- GitHub API ---
@app.route("/github", methods=["GET"])
def github_stats():
    username = request.args.get("username")
    if not username:
        return jsonify({"error": "Missing GitHub username"}), 400

    result = get_github_profile(username)
    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# from flask import Flask, request, jsonify
# from flask_cors import CORS
# from modules.codechef_module import get_codechef_stars
# from modules.geeks_for_geeks_module import get_gfg_stats
# from modules.github_module import get_github_profile
# from modules.leetcode_module import get_leetcode_full_profile
# from dotenv import load_dotenv
# import threading
# import time
# import os

# app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": "*"}})
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
#     port = int(os.environ.get("PORT", 5000))
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
# #     port = int(os.environ.get("PORT", 5000))
# #     app.run(host="0.0.0.0", port=port)
