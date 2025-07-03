from flask import Flask, request, jsonify
from modules.codechef_module import get_codechef_stars
from modules.geeks_for_geeks_module import get_gfg_stats
from modules.github_module import get_github_profile
from modules.leetcode_module import get_leetcode_solved

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ API is running. Use `/stats` with query params."
# @app.route("/debug/github", methods=["GET"])
# def debug_github():
#     try:
#         username = request.args.get("user")

#         if not username:
#             return jsonify({"error": "No username provided"}), 400

#         from modules.github_module import get_github_profile
#         print(f"🔍 Calling get_github_profile with username: {username}")
        
#         result = get_github_profile(username)
#         print(f"📦 GitHub profile result: {result}")
        
#         return jsonify(result)

#     except Exception as e:
#         print("❌ Exception in /debug/github:", str(e))
#         return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

@app.route("/stats", methods=["GET"])
def get_all_stats():
    gfg_username = request.args.get("gfg")
    leetcode_username = request.args.get("lc")
    codechef_username = request.args.get("cc")
    github_username = request.args.get("gh")

    result = {}

    try:
        if gfg_username:
            gfg_data = get_gfg_stats(gfg_username)
            result["geeksforgeeks"] = gfg_data if "error" not in gfg_data else {"error": gfg_data["error"]}
        else:
            result["geeksforgeeks"] = {"error": "No GFG username provided"}
    except Exception as e:
        result["geeksforgeeks"] = {"error": str(e)}

    try:
        if leetcode_username:
            lc_data = get_leetcode_solved(leetcode_username)
            result["leetcode"] = lc_data.get("leetcode", {"error": "Failed to parse LeetCode data"})
        else:
            result["leetcode"] = {"error": "No LeetCode username provided"}
    except Exception as e:
        result["leetcode"] = {"error": str(e)}

    try:
        if codechef_username:
            cc_data = get_codechef_stars(codechef_username)
            result["codechef"] = cc_data.get("codechef", {"error": "Failed to parse CodeChef data"})
        else:
            result["codechef"] = {"error": "No CodeChef username provided"}
    except Exception as e:
        result["codechef"] = {"error": str(e)}

    try:
        if github_username:
            gh_data = get_github_profile(github_username)
            result["github"] = gh_data.get("github", {"error": "Failed to parse GitHub data"})
        else:
            result["github"] = {"error": "No GitHub username provided"}
    except Exception as e:
        result["github"] = {"error": str(e)}

    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
