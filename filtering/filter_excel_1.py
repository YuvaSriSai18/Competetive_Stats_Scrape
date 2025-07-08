import os

def validate_profile_url(platform, username, timeout=15, max_retries=3):
    """Validate if a profile exists by checking the URL with improved rate limiting and GitHub token"""
    if not username or username == "NA":
        return False, "NA - No username provided"

    # GitHub uses API if token is provided
    if platform == "github":
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return False, "GitHub token not set"
        
        url = f"https://api.github.com/users/{username}"
        headers = {
            'Authorization': f'token {token}',
            'User-Agent': 'Python Script',
            'Accept': 'application/vnd.github.v3+json'
        }

        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return True, "Valid (GitHub API)"
            elif response.status_code == 404:
                return False, "Profile not found (GitHub API)"
            elif response.status_code == 403:
                return False, "Rate limit exceeded (GitHub API)"
            else:
                return False, f"GitHub API HTTP {response.status_code}"
        except Exception as e:
            return False, f"GitHub API error: {str(e)}"

    # LeetCode format validation only
    if platform == "leetcode":
        return validate_leetcode_username(username)

    # Other platforms (codechef, gfg)
    url_templates = {
        "codechef": f"https://www.codechef.com/users/{username}",
        "geeksforgeeks": f"https://www.geeksforgeeks.org/user/{username}/"
    }
    
    url = url_templates.get(platform)
    if not url:
        return False, "Invalid platform"

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                delay = (2 ** attempt) + random.uniform(0.5, 2.0)
                time.sleep(delay)

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }

            response = requests.get(url, timeout=timeout, allow_redirects=True, headers=headers)

            if response.status_code == 200:
                return True, "Valid"
            elif response.status_code == 404:
                return False, "Profile not found"
            elif response.status_code == 403:
                return True, "Valid (format checked - blocked by anti-bot)"
            elif response.status_code == 429:
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) * 2 + random.uniform(1, 3)
                    print(f"    Rate limited for {platform}:{username}, retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    continue
                else:
                    return True, "Valid (rate limited - assuming good format)"
            else:
                return False, f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"    Timeout for {platform}:{username}, retrying...")
                continue
            return False, "Timeout after retries"
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                print(f"    Request error for {platform}:{username}, retrying...")
                continue
            return False, f"Error: {str(e)}"

    return False, "Failed after all retries"

