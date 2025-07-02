import requests

def get_github_profile(username):
    url = f"https://api.github.com/users/{username}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"github": {"public_repos": None}}

        data = response.json()
        return {
            "github": {
                # "name": data.get("name"),
                # "bio": data.get("bio"),
                "public_repos": data.get("public_repos"),
                # "followers": data.get("followers"),
                # "following": data.get("following"),
                # "avatar_url": data.get("avatar_url"),
                # "profile_url": data.get("html_url")
            }
        }

    except Exception as e:
        return {"github": {"public_repos": None}}

# 🔧 Example usage
if __name__ == "__main__":
    username = "YuvaSriSai18"
    print(get_github_profile(username))
