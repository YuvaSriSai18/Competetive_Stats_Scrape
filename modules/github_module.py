import os
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_GRAPHQL = "https://api.github.com/graphql"
GITHUB_REST = "https://api.github.com/users"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

def get_github_profile(username):
    username = username.strip()
    if not username:
        return {"github": {"error": "Invalid or empty username"}}

    # --- Step 1: Get public repos using REST API ---
    rest_url = f"{GITHUB_REST}/{username}"
    public_repos = None

    try:
        rest_headers = {"User-Agent": "Mozilla/5.0"}
        rest_resp = requests.get(rest_url, headers=rest_headers, timeout=10)
        rest_resp.raise_for_status()
        rest_data = rest_resp.json()
        public_repos = rest_data.get("public_repos", None)
    except Exception as e:
        public_repos = None  # Still continue to GraphQL

    # --- Step 2: Get heatmap using GraphQL ---
    calendar = {}
    total_contributions = None

    if GITHUB_TOKEN:
        graphql_query = """
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
          }
        }
        """
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "User-Agent": "Mozilla/5.0"
        }
        variables = {"login": username}

        try:
            graphql_resp = requests.post(
                GITHUB_GRAPHQL,
                json={"query": graphql_query, "variables": variables},
                headers=headers,
                timeout=10
            )
            graphql_resp.raise_for_status()
            data = graphql_resp.json()

            user = data.get("data", {}).get("user")
            if user:
                contribs = user["contributionsCollection"]["contributionCalendar"]
                total_contributions = contribs.get("totalContributions", 0)

                for week in contribs.get("weeks", []):
                    for day in week["contributionDays"]:
                        date = day["date"]
                        count = day["contributionCount"]
                        if count > 0:
                            calendar[date] = count

        except Exception as e:
            return {"github": {"error": "Failed to fetch contributions. Token may be invalid."}}

    return {
        "github": {
            "profile": {
                "public_repos": public_repos,
                "total_contributions": total_contributions
            },
            "calendar": calendar
        }
    }
print(get_github_profile("yuvasrisai18"))