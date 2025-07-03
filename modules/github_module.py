import os
import requests

def get_github_profile(username):
    print(username)
    if not username or not username.strip():
        return {"github": {"error": "Invalid or empty username"}}

    url = f"https://api.github.com/users/{username.strip()}"
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    if token:
        headers["Authorization"] = f"token {token}"

    # print("📨 URL:", url)
    print("📨 Headers:", headers)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        print("📡 Status:", response.status_code)
        # print("📦 Response:", response.text)

        if response.status_code == 400:
            return {"github": {"error": "Bad Request — Check the username"}}
        elif response.status_code == 404:
            return {"github": {"error": "User not found"}}
        elif response.status_code == 403:
            return {"github": {"error": "Rate limit exceeded or forbidden"}}
        elif response.status_code != 200:
            return {"github": {"error": f"HTTP {response.status_code} \n" , "message": f"{response.json}"}}

        data = response.json()
        return {
            "github": {
                "public_repos": data.get("public_repos", 0)
            }
        }

    except Exception as e:
        return {"github": {"error": str(e)}}
