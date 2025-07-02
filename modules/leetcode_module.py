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
        "Referer": f"https://leetcode.com/u/{username}/",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.post(url, json=query, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            stats = data["data"]["matchedUser"]

            if not stats:
                return {"leetcode": {"easy": None, "medium": None, "hard": None, "total": None}}

            counts = data["data"]["matchedUser"]["submitStats"]["acSubmissionNum"]
            difficulty_counts = {item["difficulty"]: item["count"] for item in counts}

            return {
                "leetcode": {
                    "easy": difficulty_counts.get("Easy", 0),
                    "medium": difficulty_counts.get("Medium", 0),
                    "hard": difficulty_counts.get("Hard", 0),
                    "total": sum(difficulty_counts.values())
                }
            }
        else:
            return {"leetcode": {"easy": None, "medium": None, "hard": None, "total": None}}
    except Exception:
        return {"leetcode": {"easy": None, "medium": None, "hard": None, "total": None}}

# 🔧 Example usage
if __name__ == "__main__":
    username = "pranav_mudigonda"
    print(get_leetcode_solved(username))
