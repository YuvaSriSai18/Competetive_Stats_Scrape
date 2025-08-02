import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import re
from collections import defaultdict

def get_codechef_profile(username):
    """
    Scrapes CodeChef profile data including:
    - Stars, rating, max rating
    - Problems solved count
    - Badges count and detailed badge information
    - Contest participation count (with fallback methods)
    - Calendar heatmap data
    - Contest history details
    - Participated contest details with rankings, scores, and dates
    """
    url = f"https://www.codechef.com/users/{username}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
    except requests.RequestException as e:
        return {"codechef": {"error": f"Request failed: {str(e)}"}}

    soup = BeautifulSoup(res.text, "html.parser")
    profile = {}
    profile["username"] = username
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

    # 🏆 Badges Count and Details
    badges_count = 0
    badge_details = []
    
    # Method 1: Look for badges section
    badges_section = soup.find("section", class_="badges")
    if badges_section:
        badge_elements = badges_section.find_all("div", class_="badge")
        badges_count = len(badge_elements)
        for badge in badge_elements:
            badge_info = {}
            # Extract badge title
            title_elem = badge.find("span", class_="badge-title") or badge.find("h4") or badge.find("p")
            badge_info["title"] = title_elem.get_text(strip=True) if title_elem else "Unknown Badge"
            
            # Extract badge description
            desc_elem = badge.find("span", class_="badge-description") or badge.find("small")
            badge_info["description"] = desc_elem.get_text(strip=True) if desc_elem else ""
            
            # Extract badge image/icon
            img_elem = badge.find("img")
            badge_info["image"] = img_elem.get("src") if img_elem else ""
            
            # Extract any data attributes
            for attr in badge.attrs:
                if attr.startswith("data-"):
                    badge_info[attr] = badge.attrs[attr]
            
            badge_details.append(badge_info)
    
    # Method 2: Look for achievement/badge images with titles
    if badges_count == 0:
        badge_imgs = soup.find_all("img", src=re.compile(r"badge|achievement|award", re.I))
        badges_count = len(badge_imgs)
        for img in badge_imgs:
            badge_info = {}
            badge_info["title"] = img.get("alt") or img.get("title") or "Achievement Badge"
            badge_info["image"] = img.get("src", "")
            badge_info["description"] = img.get("data-original-title", "")
            badge_details.append(badge_info)
    
    # Method 3: Look for badge-related divs and spans with detailed info
    if badges_count == 0:
        badge_divs = soup.find_all("div", class_=re.compile(r"badge|achievement|award", re.I))
        badge_spans = soup.find_all("span", class_=re.compile(r"badge|achievement|award", re.I))
        all_badge_elements = badge_divs + badge_spans
        badges_count = len(all_badge_elements)
        
        for elem in all_badge_elements:
            badge_info = {}
            badge_info["title"] = elem.get_text(strip=True) or "Badge"
            badge_info["description"] = elem.get("title", "") or elem.get("data-original-title", "")
            badge_info["class"] = " ".join(elem.get("class", []))
            badge_details.append(badge_info)
    
    # Method 4: Look for text patterns indicating badges with context
    if badges_count == 0:
        badge_text = soup.find(text=re.compile(r"badges?.*earned|achievements?.*unlocked", re.I))
        if badge_text:
            parent = badge_text.parent
            if parent:
                num_match = re.search(r'(\d+)', parent.get_text())
                badges_count = int(num_match.group(1)) if num_match else 0
                # Try to extract badge names from surrounding context
                badge_container = parent.parent if parent.parent else parent
                badge_items = badge_container.find_all(["li", "div", "span"])
                for item in badge_items:
                    text = item.get_text(strip=True)
                    if text and len(text) > 3 and not text.isdigit():
                        badge_details.append({"title": text, "description": "", "type": "text_based"})
    
    # Method 5: Look for specific CodeChef badge patterns with attributes
    if badges_count == 0:
        # Look for elements with data-original-title or title containing "badge"
        badge_elements = soup.find_all(attrs={"data-original-title": re.compile(r"badge", re.I)})
        badge_elements += soup.find_all(attrs={"title": re.compile(r"badge|achievement", re.I)})
        badges_count = len(badge_elements)
        
        for elem in badge_elements:
            badge_info = {}
            badge_info["title"] = elem.get("data-original-title") or elem.get("title") or elem.get_text(strip=True)
            badge_info["description"] = elem.get("title", "") if elem.get("data-original-title") else ""
            badge_info["element_type"] = elem.name
            badge_details.append(badge_info)
    
    # Method 6: Look for CodeChef specific badge patterns (like profile badges)
    if badges_count == 0:
        # Look for profile widget or sidebar badges
        profile_widgets = soup.find_all("div", class_=re.compile(r"profile.*widget|sidebar.*widget", re.I))
        for widget in profile_widgets:
            widget_badge_elements = widget.find_all("img") + widget.find_all("div", class_=re.compile(r"badge", re.I))
            badges_count += len(widget_badge_elements)
            for badge in widget_badge_elements:
                badge_info = {}
                if badge.name == "img":
                    badge_info["title"] = badge.get("alt") or badge.get("title") or "Profile Badge"
                    badge_info["image"] = badge.get("src", "")
                else:
                    badge_info["title"] = badge.get_text(strip=True) or "Profile Badge"
                badge_info["location"] = "profile_widget"
                badge_details.append(badge_info)
    
    # Method 7: Look for star/rating based achievements
    if badges_count == 0:
        # Sometimes badges are represented as achievements based on ratings/stars
        achievement_elements = soup.find_all(["div", "span"], text=re.compile(r"★|star|achievement", re.I))
        badges_count = len(achievement_elements)
        for elem in achievement_elements:
            badge_info = {}
            badge_info["title"] = elem.get_text(strip=True)
            badge_info["type"] = "star_achievement"
            badge_info["description"] = "Star-based achievement"
            badge_details.append(badge_info)
    
    profile["badges"] = badges_count
    profile["badge_count"] = badges_count  # Alternative field name
    profile["badge_details"] = badge_details

    # 📅 Heatmap calendar
    heatmap = defaultdict(int)
    for rect in soup.select(".calendar-heatmap svg rect[data-date]"):
        dt_str = rect["data-date"]
        cnt = int(rect.get("data-count", "0") or 0)
        if cnt:
            dt = datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            heatmap[str(int(dt.timestamp()))] = cnt
    profile["calendar"] = dict(heatmap)

    # 📝 Contest Details and Participated Contest Details
    contest_details = []
    participated_contest_details = []
    
    # Method 1: Extract from contest history cards
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
        
        # Extract additional contest information
        contest["rank"] = None
        contest["score"] = None
        contest["date"] = None
        contest["problems_solved"] = None
        
        # Try to extract rank
        rank_elem = card.find(text=re.compile(r"Rank.*(\d+)", re.I))
        if rank_elem:
            rank_match = re.search(r"Rank.*?(\d+)", rank_elem, re.I)
            contest["rank"] = int(rank_match.group(1)) if rank_match else None
        
        # Try to extract score
        score_elem = card.find(text=re.compile(r"Score.*(\d+)", re.I))
        if score_elem:
            score_match = re.search(r"Score.*?(\d+)", score_elem, re.I)
            contest["score"] = int(score_match.group(1)) if score_match else None
        
        # Try to extract date
        for detail in details:
            date_match = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", detail)
            if date_match:
                contest["date"] = date_match.group(1)
                break
        
        # Try to extract problems solved count
        for detail in details:
            problems_match = re.search(r"(\d+)\s*problems?", detail, re.I)
            if problems_match:
                contest["problems_solved"] = int(problems_match.group(1))
                break
        
        # Extract all links related to the contest
        contest_links = []
        for link in card.find_all("a", href=True):
            contest_links.append({
                "text": link.get_text(strip=True),
                "url": link["href"]
            })
        contest["links"] = contest_links
        
        if contest["name"]:
            contest_details.append(contest)
            participated_contest_details.append(contest)
    
    # Method 2: Extract from contest table if available
    contest_table = soup.find("table", class_=re.compile(r"contest", re.I))
    if contest_table:
        rows = contest_table.find_all("tr")[1:]  # Skip header
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                contest = {}
                contest["name"] = cells[0].get_text(strip=True) if cells[0] else ""
                contest["rank"] = None
                contest["score"] = None
                contest["date"] = None
                
                for i, cell in enumerate(cells[1:], 1):
                    cell_text = cell.get_text(strip=True)
                    # Try to identify what this cell contains
                    if re.match(r"^\d+$", cell_text):  # Pure number might be rank or score
                        if i == 1:
                            contest["rank"] = int(cell_text)
                        elif i == 2:
                            contest["score"] = int(cell_text)
                    elif re.search(r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}", cell_text):  # Date pattern
                        contest["date"] = cell_text
                
                contest["details"] = [cell.get_text(strip=True) for cell in cells[1:]]
                contest["links"] = []
                
                if contest["name"]:
                    participated_contest_details.append(contest)
    
    # Method 3: Extract from contest rating graph data (if available)
    rating_graph = soup.find("div", id=re.compile(r"rating.*graph", re.I))
    if rating_graph:
        # Look for script tags containing contest data
        scripts = soup.find_all("script")
        for script in scripts:
            if script.string and "contest" in script.string.lower():
                # Try to extract contest data from JavaScript
                contest_data_match = re.findall(r"'([^']*contest[^']*)'", script.string, re.I)
                for contest_name in contest_data_match:
                    if len(contest_name) > 5:  # Filter out short matches
                        contest = {
                            "name": contest_name,
                            "source": "rating_graph",
                            "details": [],
                            "links": []
                        }
                        participated_contest_details.append(contest)
    
    # Method 4: Look for contest participation in user stats section
    stats_section = soup.find("div", class_=re.compile(r"user.*stats|profile.*stats", re.I))
    if stats_section:
        # Look for contest-related statistics
        contest_stats = stats_section.find_all(text=re.compile(r"contest", re.I))
        for stat_text in contest_stats:
            parent = stat_text.parent
            if parent:
                # Try to extract contest names or numbers from the context
                contest_names = re.findall(r"([A-Z][A-Za-z\s]+(?:Contest|Challenge|Cook.*Off))", parent.get_text())
                for name in contest_names:
                    contest = {
                        "name": name.strip(),
                        "source": "user_stats",
                        "details": [parent.get_text(strip=True)],
                        "links": []
                    }
                    participated_contest_details.append(contest)

    profile["contest_history"] = contest_details
    profile["participated_contests"] = participated_contest_details

    # 🏁 Contest Participation Count and Contest Count
    contests_participated = 0
    contest_count = len(participated_contest_details)  # Count from extracted participated contest details
    
    # Try to find contest participation count
    contest_participation = soup.find("div", class_="contest-participated-count")
    if contest_participation:
        b_tag = contest_participation.find("b")
        if b_tag and b_tag.text.strip().isdigit():
            contests_participated = int(b_tag.text.strip())
    
    # Alternative method 1: Look for text patterns
    if contests_participated == 0:
        contests_text = soup.find(text=re.compile(r"Contests.*Participated", re.I))
        if contests_text:
            parent = contests_text.parent
            if parent:
                num_match = re.search(r'(\d+)', parent.get_text())
                contests_participated = int(num_match.group(1)) if num_match else 0
    
    # Alternative method 2: Look for specific contest stats elements
    if contests_participated == 0:
        contest_stats = soup.find_all("div", class_=re.compile(r"contest.*stat", re.I))
        for stat in contest_stats:
            text = stat.get_text()
            if re.search(r"participat", text, re.I):
                num_match = re.search(r'(\d+)', text)
                if num_match:
                    contests_participated = int(num_match.group(1))
                    break
    
    # Alternative method 3: Look for contest numbers in various elements
    if contests_participated == 0:
        # Look for numbers in elements that might contain contest info
        for elem in soup.find_all(["span", "div", "p"], text=re.compile(r'\d+')):
            parent_text = elem.parent.get_text() if elem.parent else elem.get_text()
            if re.search(r"contest.*\d+|participat.*\d+", parent_text, re.I):
                num_match = re.search(r'(\d+)', elem.get_text())
                if num_match:
                    contests_participated = int(num_match.group(1))
                    break
    
    # Fallback: use participated contest details count if still 0
    if contests_participated == 0:
        contests_participated = contest_count
    
    profile["contests_participated"] = contests_participated
    profile["contest_count"] = contest_count

    return {"codechef": profile}

# ✅ Test
if __name__ == "__main__":
    username = "dhanush_730"
    import json
    print(json.dumps(get_codechef_profile(username), indent=4))