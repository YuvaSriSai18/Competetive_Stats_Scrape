import requests
from datetime import datetime
from collections import defaultdict

def get_leetcode_full_profile(username):
    url = "https://leetcode.com/graphql"
    headers = {
        "Content-Type": "application/json",
        "Referer": f"https://leetcode.com/{username}/",
        "User-Agent": "Mozilla/5.0"
    }

    result = {
        "calendar": {},
        "profile": {
            "username": username,
            "problems_solved": [],
            "badges": [],
            "contest_history": [],
            "contest_ranking": {}
        }
    }

    try:
        # Heatmap
        heatmap_query = {
            "query": """
            query recentAc($username: String!) {
              recentAcSubmissionList(username: $username, limit: 1000) {
                timestamp
              }
            }
            """,
            "variables": {"username": username}
        }
        resp = requests.post(url, json=heatmap_query, headers=headers, timeout=10)
        resp.raise_for_status()

        subs = resp.json().get("data", {}).get("recentAcSubmissionList", [])
        calendar = defaultdict(int)
        for sub in subs:
            ts = int(sub["timestamp"])
            day = datetime.utcfromtimestamp(ts).replace(hour=0, minute=0, second=0, microsecond=0)
            calendar[str(int(day.timestamp()))] += 1
        result["calendar"] = dict(calendar)

        # Full profile including badges and contests
        profile_query = {
            "query": """
            query userProfile($username: String!) {
              allQuestionsCount {
                difficulty
                count
              }
              matchedUser(username: $username) {
                username
                submitStatsGlobal {
                  acSubmissionNum {
                    difficulty
                    count
                  }
                }
                badges {
                  id
                  displayName
                  icon
                }
              }
              userContestRanking(username: $username) {
                attendedContestsCount
                rating
                globalRanking
                totalParticipants
                topPercentage
              }
              userContestRankingHistory(username: $username) {
                attended
                rating
                ranking
                contest {
                  title
                  startTime
                }
              }
            }
            """,
            "variables": {"username": username}
        }
        resp2 = requests.post(url, json=profile_query, headers=headers, timeout=10)
        resp2.raise_for_status()
        pd = resp2.json().get("data", {})

        mu = pd.get("matchedUser", {})
        result["profile"]["username"] = mu.get("username", "")

        # Problems solved
        ac = mu.get("submitStatsGlobal", {}).get("acSubmissionNum", [])
        result["profile"]["problems_solved"] = [
            {"difficulty": item["difficulty"], "count": item["count"]}
            for item in ac
        ]

        # Badges
        result["profile"]["badges"] = [
            {"id": b.get("id"), "displayName": b.get("displayName"), "icon": b.get("icon")}
            for b in mu.get("badges", [])
        ]

        # Contest ranking
        cr = pd.get("userContestRanking", {})
        if cr:
            result["profile"]["contest_ranking"] = {
                "attendedContestsCount": cr.get("attendedContestsCount", 0),
                "rating": cr.get("rating", 0),
                "globalRanking": cr.get("globalRanking", 0),
                "totalParticipants": cr.get("totalParticipants", 0),
                "topPercentage": cr.get("topPercentage", 0)
            }

        # Contest history
        history = pd.get("userContestRankingHistory", [])
        result["profile"]["contest_history"] = [
            {
                "title": h["contest"].get("title"),
                "startTime": datetime.utcfromtimestamp(int(h["contest"]["startTime"])).strftime("%Y-%m-%d"),
                "rating": h.get("rating"),
                "ranking": h.get("ranking")
            }
            for h in history if h.get("attended")
        ]

    except Exception as e:
        print("Error:", e)

    return result

if __name__ == "__main__":
    from pprint import pprint
    pprint(get_leetcode_full_profile("Yuva_SriSai_18"))
