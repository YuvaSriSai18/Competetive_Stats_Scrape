import requests
from bs4 import BeautifulSoup

def get_codechef_stars(username):
    url = f"https://www.codechef.com/users/{username}"
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return {"codechef": {"stars": None}}

    soup = BeautifulSoup(response.text, 'html.parser')
    rating_header = soup.find('div', class_='rating-header')

    if rating_header:
        all_divs = rating_header.find_all('div')
        for div in all_divs:
            if '★' in div.text:
                stars = div.text.strip()
                return {"codechef": {"stars": stars.count('★')}}

    return {"codechef": {"stars": None}}

# 🔧 Example usage
if __name__ == "__main__":
    username = "dhanush_730"
    data = get_codechef_stars(username)
    print(data)
