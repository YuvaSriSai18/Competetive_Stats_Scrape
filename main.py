import json
from modules.codechef_module import get_codechef_stars
from modules.geeks_for_geeks_module import get_gfg_stats
from modules.github_module import get_github_profile
from modules.leetcode_module import get_leetcode_solved

def get_all_stats(gfg_username, leetcode_username, codechef_username, github_username):
    result = {}

    try:
        gfg_data = get_gfg_stats(gfg_username)
        result["geeksforgeeks"] = gfg_data if "error" not in gfg_data else {"error": gfg_data["error"]}
    except Exception as e:
        result["geeksforgeeks"] = {"error": str(e)}

    try:
        lc_data = get_leetcode_solved(leetcode_username)
        result["leetcode"] = lc_data.get("leetcode", {"error": "Failed to parse LeetCode data"})
    except Exception as e:
        result["leetcode"] = {"error": str(e)}

    try:
        cc_data = get_codechef_stars(codechef_username)
        result["codechef"] = cc_data.get("codechef", {"error": "Failed to parse CodeChef data"})
    except Exception as e:
        result["codechef"] = {"error": str(e)}

    try:
        gh_data = get_github_profile(github_username)
        result["github"] = gh_data.get("github", {"error": "Failed to parse GitHub data"})
    except Exception as e:
        result["github"] = {"error": str(e)}

    return result

# ✅ Example usage
if __name__ == "__main__":
    gfg_username = "yuvasrisai18"
    leetcode_username = "Yuva_SriSai_18"
    codechef_username = "yuvasrisai"
    github_username = "YuvaSriSai18"

    profile_stats = get_all_stats(
        gfg_username=gfg_username,
        leetcode_username=leetcode_username,
        codechef_username=codechef_username,
        github_username=github_username
    )

    print(json.dumps(profile_stats, indent=4))
