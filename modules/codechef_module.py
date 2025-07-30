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

    # 📊 Rating and max rating
    rating = soup.find("div", class_="rating-number")
    profile["rating"] = float(rating.text.strip()) if rating else None

    max_tag = rating.find_next_sibling("small") if rating else None
    if max_tag:
        m = re.search(r'(\d+)', max_tag.text)
        profile["max_rating"] = float(m.group(1)) if m else None
    else:
        profile["max_rating"] = None

    # ✅ Total Problems Solved
    prob_tag = soup.find("h3", string=re.compile("Total Problems Solved"))
    if prob_tag:
        num_text = re.sub(r"\D", "", prob_tag.text)
        profile["problems_solved"] = int(num_text) if num_text else 0
    else:
        profile["problems_solved"] = 0

    # 📅 Heatmap calendar
    heatmap = defaultdict(int)
    for rect in soup.select(".calendar-heatmap svg rect[data-date]"):
        dt_str = rect["data-date"]
        cnt = int(rect.get("data-count", "0") or 0)
        if cnt:
            dt = datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            heatmap[str(int(dt.timestamp()))] = cnt
    profile["calendar"] = dict(heatmap)

    # 🏁 Contest Participation Count
    contest_participation = soup.find("div", class_="contest-participated-count")
    if contest_participation:
        b_tag = contest_participation.find("b")
        if b_tag and b_tag.text.strip().isdigit():
            profile["contests_participated"] = int(b_tag.text.strip())
        else:
            profile["contests_participated"] = 0
    else:
        profile["contests_participated"] = 0

    # 📝 Contest Details
    contest_details = []
    cards = soup.find_all("div", class_="content")
    for card in cards:
        h5 = card.find("h5")
        if not h5:
            continue
        contest = {}
        contest["name"] = h5.get_text(strip=True)
        
        details = []
        for span in card.find_all("span", style=lambda value: value and "font-size: 12px" in value):
            detail = span.get_text(strip=True)
            if detail:
                details.append(detail)
        contest["details"] = details
        if contest["name"]:
            contest_details.append(contest)

    profile["contest_history"] = contest_details

    return {"codechef": profile}

# ✅ Test
if __name__ == "__main__":
    username = "dhanush_730"
    import json
    print(json.dumps(get_codechef_profile(username), indent=4))
