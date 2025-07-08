import pandas as pd
import requests
import re
import time
import random
from urllib.parse import urlparse
import concurrent.futures
from threading import Lock
import threading
import string
import os
# GitHub Access Token (set your own token here)
GITHUB_TOKEN =  os.environ.get("GITHUB_TOKEN", "").strip()

print_lock = Lock()

def normalize_na_values(value):
    if pd.isna(value) or not isinstance(value, str):
        return "NA"
    value = value.strip()
    na_values = {
        "", "na", "null", "none", "no link", "not available", "notavailable",
        "n/a", "N/A", "Na", "NA", "No", "no", "None", "nil", "NIL"
    }
    return "NA" if value.lower() in [v.lower() for v in na_values] else value

def extract_username_from_url_or_text(platform, raw_input):
    if not raw_input or raw_input == "NA":
        return "NA"
    raw_input = raw_input.strip()
    patterns = {
        "leetcode": [r"leetcode\.com/u/([^/\s\?]+)", r"leetcode\.com/([^/\s\?]+)", r"leetcode\.com/profile/([^/\s\?]+)"],
        "codechef": [r"codechef\.com/users/([^/\s\?]+)", r"codechef\.com/user/([^/\s\?]+)"],
        "geeksforgeeks": [r"geeksforgeeks\.org/user/([^/\s\?]+)", r"geeksforgeeks\.org/profile/([^/\s\?]+)"],
        "github": [r"github\.com/([^/\s\?]+)"]
    }
    for pattern in patterns.get(platform, []):
        match = re.search(pattern, raw_input, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return raw_input.strip() if not any(x in raw_input for x in ['http', '/', '.com', '.org']) else "NA"

def validate_profile_url(platform, username, timeout=15, max_retries=3):
    if not username or username == "NA":
        return False, "NA - No username provided"
    if platform == "leetcode":
        return validate_leetcode_username(username)
    if platform == "github":
        return validate_github(username)
    if platform == "codechef":
        return validate_codechef(username)

    url_templates = {
        "geeksforgeeks": f"https://www.geeksforgeeks.org/user/{username}/"
    }

    url = url_templates.get(platform)
    if not url:
        return False, "Invalid platform"

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep((2 ** attempt) + random.uniform(0.5, 2.0))

            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'text/html',
                'Connection': 'keep-alive'
            }

            response = requests.get(url, timeout=timeout, headers=headers)
            if response.status_code == 200:
                return True, "Valid"
            elif response.status_code == 404:
                return False, "Profile not found"
            elif response.status_code == 403:
                return True, "Valid (403 - bot protection)"
            elif response.status_code == 429:
                time.sleep((2 ** attempt) + 1)
                continue
            else:
                return False, f"HTTP {response.status_code}"
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                continue
            return False, f"Error: {e}"
    return False, "Retries exhausted"

def validate_leetcode_username(username):
    if not username or username == "NA":
        return False, "NA - No username"
    allowed_chars = string.ascii_letters + string.digits + "_-"
    if not all(c in allowed_chars for c in username):
        return False, "Invalid characters"
    if len(username) < 3 or len(username) > 30:
        return False, "Invalid length"
    return True, "Format valid (LeetCode blocks bots)"

def validate_github(username):
    url = f"https://api.github.com/users/{username}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GitHub-Username-Checker"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return True, "Valid"
        elif response.status_code == 404:
            return False, "Not found"
        elif response.status_code == 403:
            return True, "Rate limited but format valid"
        else:
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, f"Error: {e}"

def validate_codechef(username):
    url = f"https://www.codechef.com/users/{username}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if response.status_code == 200:
            if "404 - Page Not Found" in response.text or "User not found" in response.text:
                return False, "Profile not found"
            return True, "Valid"
        elif response.status_code == 404:
            return False, "Profile not found"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, f"Error: {e}"

def process_row_threaded(row, idx, total_rows, platforms, results_dict, results_lock):
    try:
        print(f"\n[{idx + 1}/{total_rows}] Processing {row.get('RollNo', 'Unknown')}...")
        result = process_single_profile(row.to_dict(), platforms)
        output_row = {
            'RollNo': row.get('RollNo', ''),
            'email': row.get('email', ''),
            'name': row.get('name', ''),
            'leetcode(username)': result.get('leetcode_username', 'NA'),
            'codechef(username)': result.get('codechef_username', 'NA'), 
            'geeksforgeeks(username)': result.get('geeksforgeeks_username', 'NA'),
            'github(username)': result.get('github_username', 'NA'),
            'Validation': result.get('validation', 'invalid')
        }
        with results_lock:
            results_dict[idx] = output_row
    except Exception as e:
        print(f"Error in row {idx + 1}: {e}")
        with results_lock:
            results_dict[idx] = {
                'RollNo': row.get('RollNo', ''),
                'email': row.get('email', ''),
                'name': row.get('name', ''),
                'leetcode(username)': 'ERROR',
                'codechef(username)': 'ERROR', 
                'geeksforgeeks(username)': 'ERROR',
                'github(username)': 'ERROR',
                'Validation': 'error'
            }

def process_single_profile(row_data, platforms):
    results = {}
    validation_results = {}
    invalid_platforms = []
    valid_count = 0

    time.sleep(random.uniform(0.5, 1.0))

    for platform in platforms:
        raw_value = normalize_na_values(row_data.get(platform, "NA"))
        if raw_value == "NA":
            results[f"{platform}_username"] = "NA"
            validation_results[platform] = "NA"
            continue

        username = extract_username_from_url_or_text(platform, raw_value)
        results[f"{platform}_username"] = username
        if username == "NA":
            validation_results[platform] = "invalid"
            invalid_platforms.append(platform)
            continue

        is_valid, status = validate_profile_url(platform, username)
        if platform == "leetcode" and "Format valid" in status:
            validation_results[platform] = "valid"
            valid_count += 1
        elif is_valid:
            validation_results[platform] = "valid"
            valid_count += 1
        else:
            validation_results[platform] = "invalid"
            invalid_platforms.append(platform)

        with print_lock:
            print(f"  {platform}: {username} -> {'[Valid]' if is_valid else '[Invalid]'} ({status})")

    if valid_count > 0 and len(invalid_platforms) == 0:
        overall = "valid"
    elif valid_count > 0:
        overall = f"invalid({','.join(invalid_platforms)})"
    elif len(invalid_platforms) > 0:
        overall = f"invalid({','.join(invalid_platforms)})"
    else:
        overall = "invalid"

    results["validation"] = overall
    results["validation_details"] = validation_results
    return results

def main():
    input_file = r"D:\Projects\Personel\Competetive_Stats_Scrape\filtering\filtering.csv"
    output_file = "data.csv"
    print(">> Starting Profile Validation Process...")
    try:
        df = pd.read_csv(input_file)
        column_mapping = {
            'RollNo': 'RollNo', 'email': 'email', 'Name': 'name',
            'LeetCode': 'leetcode', 'codeChef': 'codechef',
            'geeksForGeeks': 'geeksforgeeks', 'github': 'github'
        }
        df = df.rename(columns=column_mapping)
        platforms = ['leetcode', 'codechef', 'geeksforgeeks', 'github']
        results_dict = {}
        results_lock = threading.Lock()
        max_workers = 5

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(process_row_threaded, row, idx, len(df), platforms, results_dict, results_lock): idx
                for idx, row in df.iterrows()
            }
            for future in concurrent.futures.as_completed(future_to_idx):
                future.result()

        output_df = pd.DataFrame([results_dict[i] for i in sorted(results_dict)])
        output_df.to_csv(output_file, index=False)

        print(f"\n>> SUMMARY:\n   Total rows: {len(output_df)}")
        print(f"   Valid profiles: {len(output_df[output_df['Validation'] == 'valid'])}")
        invalid_profiles = output_df[output_df['Validation'].str.startswith('invalid')]
        print(f"   Invalid profiles: {len(invalid_profiles)}")
        for val, count in invalid_profiles['Validation'].value_counts().items():
            print(f"     - {val}: {count}")
        print("\n>> Process complete.")

    except Exception as e:
        print(f"XX Error: {e}")

if __name__ == "__main__":
    main()
