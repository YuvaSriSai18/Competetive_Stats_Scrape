import requests
import json
from bs4 import BeautifulSoup as bs

def get_gfg_stats(username):
    PRACTICE_URL = f'https://auth.geeksforgeeks.org/user/{username}/practice/'
    PROFILE_URL = f'https://www.geeksforgeeks.org/user/{username}/'

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    # 1. Get practice page for problem stats
    profilePage = requests.get(PRACTICE_URL, headers=headers)
    if profilePage.status_code != 200:
        return {"error": "Practice profile not found"}

    soup = bs(profilePage.content, 'html.parser')

    script_tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script_tag:
        return {"error": "Could not find user data script"}

    try:
        user_data = json.loads(script_tag.string)
        user_info = user_data["props"]["pageProps"]["userInfo"]
        user_submissions = user_data["props"]["pageProps"]["userSubmissionsInfo"]
    except (KeyError, json.JSONDecodeError):
        return {"error": "Failed to parse user data"}

    generalInfo = {
        "userName": username,
        "fullName": user_info.get("name", ""),
        "profilePicture": user_info.get("profile_image_url", ""),
        "institute": user_info.get("institute_name", ""),
        "instituteRank": user_info.get("institute_rank", ""),
        "currentStreak": user_info.get("pod_solved_longest_streak", "00"),
        "maxStreak": user_info.get("pod_solved_global_longest_streak", "00"),
        "codingScore": user_info.get("score", 0),
        "monthlyScore": user_info.get("monthly_score", 0),
        "totalProblemsSolved": user_info.get("total_problems_solved", 0),
        "contestRating": None  # placeholder
    }

    solvedStats = {}
    for difficulty, problems in user_submissions.items():
        solvedStats[difficulty.lower()] = {
            "count": len(problems)
        }

    # 2. Get profile page for contest rating
    profilePage2 = requests.get(PROFILE_URL, headers=headers)
    if profilePage2.status_code == 200:
        soup2 = bs(profilePage2.content, 'html.parser')
        try:
            rating_element = soup2.find('div', string='Contest Rating')
            if rating_element:
                rating_value = rating_element.find_next('div')
                if rating_value:
                    generalInfo["contestRating"] = int(rating_value.text.strip())
        except Exception as e:
            generalInfo["contestRating"] = None

    return {
        "info": generalInfo,
        "solvedStats": solvedStats
    }


# Example direct call to test the module
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = input("Enter GFG username: ")

    data = get_gfg_stats(username)

    if "error" in data:
        print("❌", data["error"])
    else:
        print(json.dumps(data, indent=4))