import requests
from datetime import datetime, timedelta
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
        # Heatmap - Try to get submission calendar data
        heatmap_query = {
            "query": """
            query userProfileCalendar($username: String!, $year: Int!) {
              matchedUser(username: $username) {
                userCalendar(year: $year) {
                  activeYears
                  streak
                  totalActiveDays
                  submissionCalendar
                }
              }
            }
            """,
            "variables": {"username": username, "year": datetime.now().year}
        }
        
        resp = requests.post(url, json=heatmap_query, headers=headers, timeout=10)
        resp.raise_for_status()
        calendar_data = resp.json().get("data", {})
        
        # Initialize calendar for the past year
        today = datetime.now()
        start_date = today - timedelta(days=365)
        calendar = {}
        current_date = start_date
        while current_date <= today:
            date_str = current_date.strftime("%Y-%m-%d")
            calendar[date_str] = 0
            current_date += timedelta(days=1)
        
        # Try to parse submission calendar if available
        user_data = calendar_data.get("matchedUser")
        if user_data and user_data.get("userCalendar"):
            submission_calendar = user_data["userCalendar"].get("submissionCalendar")
            if submission_calendar:
                # submissionCalendar is a JSON string with timestamp: count pairs
                import json
                try:
                    calendar_dict = json.loads(submission_calendar)
                    for timestamp_str, count in calendar_dict.items():
                        ts = int(timestamp_str)
                        date = datetime.utcfromtimestamp(ts)
                        date_str = date.strftime("%Y-%m-%d")
                        if date_str in calendar:
                            calendar[date_str] = count
                except:
                    print("Failed to parse submission calendar, falling back to recent submissions")
        
        # Fallback: Use recent submissions if calendar data not available
        if not any(count > 0 for count in calendar.values()):
            print("No calendar data found, trying recent submissions approach...")
            fallback_query = {
                "query": """
                query recentAc($username: String!) {
                  recentAcSubmissionList(username: $username, limit: 5000) {
                    timestamp
                  }
                }
                """,
                "variables": {"username": username}
            }
            resp2 = requests.post(url, json=fallback_query, headers=headers, timeout=10)
            resp2.raise_for_status()
            
            subs = resp2.json().get("data", {}).get("recentAcSubmissionList", [])
            submission_count = 0
            
            for sub in subs:
                ts = int(sub["timestamp"])
                submission_date = datetime.utcfromtimestamp(ts)
                date_str = submission_date.strftime("%Y-%m-%d")
                
                if date_str in calendar:
                    calendar[date_str] += 1
                    submission_count += 1
            
            print(f"Fallback: Processed {submission_count} submissions from {len(subs)} total")
        
        result["calendar"] = calendar

        # Full profile including badges and contests
        # Update profile_query to include aboutMe
        profile_query = {
            "query": """
            query userProfile($username: String!) {
              allQuestionsCount {
                difficulty
                count
              }
              matchedUser(username: $username) {
                username
                profile {
                  aboutMe
                }
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
        result["profile"]["bio"] = mu.get("profile", {}).get("aboutMe", "")


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
