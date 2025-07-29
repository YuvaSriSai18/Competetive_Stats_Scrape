import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import re
from collections import defaultdict

def get_codechef_profile(username):
    url = f"https://www.codechef.com/users/{username}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
    except requests.RequestException as e:
        return {"codechef": {"error": f"Request failed: {str(e)}"}}

    soup = BeautifulSoup(res.text, "html.parser")
    profile = {}

    # ⭐ Stars
    rating_header = soup.find("div", class_="rating-header")
    profile["stars"] = rating_header.get_text().count("★") if rating_header else 0

    # 🏆 Rating and Max Rating
    rating = soup.find("div", class_="rating-number")
    profile["rating"] = float(rating.text.strip()) if rating else None

    max_tag = rating.find_next_sibling("small") if rating else None
    if max_tag:
        max_text = max_tag.text.strip()
        match = re.search(r'(\d+)', max_text)
        profile["max_rating"] = float(match.group(1)) if match else None
    else:
        profile["max_rating"] = None

    # ✅ Problems solved
    solved_sec = soup.find("section", id="problem-solved")
    if solved_sec:
        count_tag = solved_sec.find("h5")
        num = re.sub(r'\D', '', count_tag.text or "")
        profile["problems_solved"] = int(num) if num else 0
    else:
        profile["problems_solved"] = 0

    # 📅 Heatmap (calendar)
    heatmap = defaultdict(int)
    for rect in soup.select(".calendar-heatmap svg rect[data-date]"):
        date = rect["data-date"]
        count = int(rect.get("data-count", "0") or 0)
        if count:
            dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            heatmap[str(int(dt.timestamp()))] = count
    profile["calendar"] = dict(heatmap)

    # 📊 Estimated contests participated
    rating_graph_paths = soup.select(".rating-graph path")
    profile["contests_participated"] = len(rating_graph_paths)

    return {"codechef": profile}

# ✅ Test
if __name__ == "__main__":
    username = "dhanush_730"  # replace with your username
    result = get_codechef_profile(username)
    print(result)
