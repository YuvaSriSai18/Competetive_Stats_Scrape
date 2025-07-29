# modules/github_module.py
import os
import requests
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

GITHUB_GRAPHQL = "https://api.github.com/graphql"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

def get_github_profile(username):
    print(f"1 : {GITHUB_TOKEN}")
    if not username or not username.strip():
        return {"github": {"error": "Invalid or empty username"}}
    print(f"2 : {GITHUB_TOKEN}")
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "User-Agent": "Mozilla/5.0"
    }

    # GraphQL query for profile + heatmap
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
        publicRepos: repositories(privacy: PUBLIC) {
          totalCount
        }
      }
    }
    """
    variables = {"login": username.strip()}

    try:
        resp = requests.post(GITHUB_GRAPHQL, json={"query": query, "variables": variables}, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        user = data.get("data", {}).get("user")
        if not user:
            return {"github": {"error": "User not found"}}

        # Process calendar data
        weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
        calendar = {}
        for week in weeks:
            for day in week["contributionDays"]:
                date = day["date"]  # YYYY‑MM‑DD
                calendar[date] = day["contributionCount"]

        profile = {
            "public_repos": user["publicRepos"]["totalCount"],
            "total_contributions": user["contributionsCollection"]["contributionCalendar"]["totalContributions"]
        }

        return {"github": {"profile": profile, "calendar": calendar}}

    except Exception as e:
        return {"github": {"error": str(e)}}
