import requests

def get_leetcode_solved(username):
    url = "https://leetcode.com/graphql"
    query = {
        "query": """
        query getUserProfile($username: String!) {
          matchedUser(username: $username) {
            submitStats {
              acSubmissionNum {
                difficulty
                count
              }
            }
          }
        }
        """,
        "variables": {
            "username": username
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Referer": f"https://leetcode.com/{username}/",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.post(url, json=query, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        matched_user = data.get("data", {}).get("matchedUser")
        if not matched_user or not matched_user.get("submitStats"):
            return {"leetcode": {"easy": None, "medium": None, "hard": None, "total": None}}

        counts = matched_user["submitStats"].get("acSubmissionNum", [])
        difficulty_counts = {item["difficulty"]: item["count"] for item in counts}
        
        easy = difficulty_counts.get("Easy", 0)
        medium = difficulty_counts.get("Medium", 0)
        hard = difficulty_counts.get("Hard", 0)

        return {
            "leetcode": {
                "easy": easy,
                "medium": medium,
                "hard": hard,
                "total": easy + medium + hard
            }
        }
    except Exception as e:
        print(f"Error fetching LeetCode stats: {e}")
        return {"leetcode": {"easy": None, "medium": None, "hard": None, "total": None}}

# 🔧 Example usage
if __name__ == "__main__":
    username = "pranav_mudigonda"
    print(get_leetcode_solved(username))