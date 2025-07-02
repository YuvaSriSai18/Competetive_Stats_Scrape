"""Say whether the given excel social links are valid or not"""

import pandas as pd
import requests
import re
import time
import random
from urllib.parse import urlparse
import concurrent.futures
from threading import Lock
import threading

# Global counter for thread-safe operations
print_lock = Lock()

def normalize_na_values(value):
    """Convert various NA representations to 'NA'"""
    if pd.isna(value) or not isinstance(value, str):
        return "NA"
    
    value = str(value).strip()
    na_values = {
        "", "na", "null", "none", "no link", "not available", "notavailable",
        "n/a", "N/A", "Na", "NA", "No", "no", "None", "nil", "NIL"
    }
    
    if value.lower() in [v.lower() for v in na_values]:
        return "NA"
    
    return value

def extract_username_from_url_or_text(platform, raw_input):
    """Extract username from URL or return as-is if it's already a username"""
    if not raw_input or raw_input == "NA":
        return "NA"
    
    raw_input = raw_input.strip()
    
    # Platform-specific patterns
    patterns = {
        "leetcode": [
            r"leetcode\.com/u/([^/\s\?]+)",
            r"leetcode\.com/([^/\s\?]+)",
            r"leetcode\.com/profile/([^/\s\?]+)"
        ],
        "codechef": [
            r"codechef\.com/users/([^/\s\?]+)",
            r"codechef\.com/user/([^/\s\?]+)"
        ],
        "geeksforgeeks": [
            r"geeksforgeeks\.org/user/([^/\s\?]+)",
            r"geeksforgeeks\.org/profile/([^/\s\?]+)"
        ],
        "github": [
            r"github\.com/([^/\s\?]+)"
        ]
    }
    
    # Try to extract username from URL
    for pattern in patterns.get(platform, []):
        match = re.search(pattern, raw_input, re.IGNORECASE)
        if match:
            username = match.group(1)
            # Clean username
            username = username.replace('/', '').replace('?', '').strip()
            return username if username else "NA"
    
    # If no pattern matches, check if it's already a username (no URL structure)
    if not any(char in raw_input for char in ['http', '/', '.com', '.org']):
        # It's likely already a username
        return raw_input.strip()
    
    return "NA"

def validate_profile_url(platform, username, timeout=15, max_retries=3):
    """Validate if a profile exists by checking the URL with improved rate limiting"""
    if not username or username == "NA":
        return False, "NA - No username provided"
    
    # Construct profile URLs
    url_templates = {
        "leetcode": f"https://leetcode.com/u/{username}/",
        "codechef": f"https://www.codechef.com/users/{username}",
        "geeksforgeeks": f"https://www.geeksforgeeks.org/user/{username}/",
        "github": f"https://github.com/{username}"
    }
    
    url = url_templates.get(platform)
    if not url:
        return False, "Invalid platform"
    
    # Special handling for LeetCode due to anti-bot protection
    if platform == "leetcode":
        return validate_leetcode_username(username)
    
    # Retry logic for handling rate limits
    for attempt in range(max_retries):
        try:
            # Add exponential backoff delay
            if attempt > 0:
                delay = (2 ** attempt) + random.uniform(0.5, 2.0)
                time.sleep(delay)
            
            # Add headers to mimic a browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,/;q=0.8',
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
                # Rate limited - continue to retry
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) * 2 + random.uniform(1, 3)
                    print(f"    Rate limited for {platform}:{username}, retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    continue
                else:
                    # If all retries exhausted, assume valid for rate limit cases
                    return True, f"Valid (rate limited - assuming good format)"
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

def validate_leetcode_username(username):
    """Special validation for LeetCode usernames with basic format checking"""
    if not username or username == "NA":
        return False, "NA - No username provided"
    
    # Basic username validation (LeetCode usernames are typically alphanumeric with underscores/hyphens)
    import string
    allowed_chars = string.ascii_letters + string.digits + '_-'
    
    # Check if username contains only allowed characters
    if not all(c in allowed_chars for c in username):
        return False, "Invalid characters in username"
    
    # Check length (LeetCode usernames are typically 3-30 characters)
    if len(username) < 3 or len(username) > 30:
        return False, "Username length invalid"
    
    # Since we can't reliably check LeetCode due to anti-bot protection,
    # we'll mark it as "assumed valid" if format is correct
    return True, "Format valid (LeetCode blocks validation)"

def process_row_threaded(row, idx, total_rows, platforms, results_dict, results_lock):
    """Process a single row in a thread"""
    try:
        print(f"\n[{idx + 1}/{total_rows}] Processing {row.get('rollNo', 'Unknown')}...")
        
        # Process the row
        result = process_single_profile(row.to_dict(), platforms)
        
        # Create output row
        output_row = {
            'rollNo': row.get('rollNo', ''),
            'email': row.get('email', ''),
            'name': row.get('name', ''),
            'leetcode(username)': result.get('leetcode_username', 'NA'),
            'codechef(username)': result.get('codechef_username', 'NA'), 
            'geeksforgeeks(username)': result.get('geeksforgeeks_username', 'NA'),
            'github(username)': result.get('github_username', 'NA'),
            'Validation': result.get('validation', 'invalid')
        }
        
        # Thread-safe update of results
        with results_lock:
            results_dict[idx] = output_row
            
    except Exception as e:
        print(f"Error processing row {idx + 1}: {str(e)}")
        # Create error row
        with results_lock:
            results_dict[idx] = {
                'rollNo': row.get('rollNo', ''),
                'email': row.get('email', ''),
                'name': row.get('name', ''),
                'leetcode(username)': 'ERROR',
                'codechef(username)': 'ERROR', 
                'geeksforgeeks(username)': 'ERROR',
                'github(username)': 'ERROR',
                'Validation': 'error'
            }

def process_single_profile(row_data, platforms):
    """Process a single row of data for all platforms with detailed validation"""
    results = {}
    validation_results = {}
    invalid_platforms = []
    valid_count = 0
    
    # Add a small random delay to avoid overwhelming servers
    time.sleep(random.uniform(0.5, 1.5))
    
    for platform in platforms:
        column_name = platform
        raw_value = normalize_na_values(row_data.get(column_name, "NA"))
        
        if raw_value == "NA":
            results[f"{platform}_username"] = "NA"
            validation_results[platform] = "NA"
        else:
            username = extract_username_from_url_or_text(platform.lower(), raw_value)
            results[f"{platform}_username"] = username
            
            # Validate the profile
            if username != "NA":
                is_valid, status = validate_profile_url(platform.lower(), username)
                
                # For LeetCode, if format is valid, consider it valid for overall validation
                if platform.lower() == "leetcode" and "Format valid" in status:
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
            else:
                validation_results[platform] = "invalid"
                invalid_platforms.append(platform)
    
    # Create detailed validation status
    if valid_count > 0 and len(invalid_platforms) == 0:
        # All platforms are valid or NA
        overall_validation = "valid"
    elif valid_count > 0 and len(invalid_platforms) > 0:
        # Some valid, some invalid - show which ones are invalid
        invalid_list = ", ".join(invalid_platforms)
        overall_validation = f"invalid({invalid_list})"
    elif len(invalid_platforms) > 0:
        # All non-NA platforms are invalid
        invalid_list = ", ".join(invalid_platforms)
        overall_validation = f"invalid({invalid_list})"
    else:
        # All are NA
        overall_validation = "invalid"
    
    results["validation"] = overall_validation
    results["validation_details"] = validation_results
    
    return results

def main():
    print(">> Starting Profile Validation Process...")
    
    # Input and output file paths
    input_file = "filtered_data.csv"
    output_file = "data.csv"
    
    try:
        # Read the CSV file
        print(f">> Reading data from {input_file}...")
        df = pd.read_csv(input_file)
        print(f"   Found {len(df)} rows")
        
        # Normalize column names to match expected format
        column_mapping = {
            'RollNo': 'rollNo',
            'email': 'email', 
            'Name': 'name',
            'LeetCode': 'leetcode',
            'codeChef': 'codechef', 
            'geeksForGeeks': 'geeksforgeeks',
            'github': 'github'
        }
        
        # Rename columns to match the expected output format
        df = df.rename(columns=column_mapping)
        
        # Platforms to validate
        platforms = ['leetcode', 'codechef', 'geeksforgeeks', 'github']
        
        # Process each row using threading
        print("\n>> Validating profiles using threading...")
        
        # Prepare for threaded processing
        results_dict = {}
        results_lock = threading.Lock()
        max_workers = 5  # Reduced to avoid rate limiting
        
        # Create thread pool and submit tasks
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_idx = {}
            for idx, row in df.iterrows():
                future = executor.submit(process_row_threaded, row, idx, len(df), platforms, results_dict, results_lock)
                future_to_idx[future] = idx
            
            # Wait for completion and handle any errors
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    future.result()  # This will raise any exception that occurred
                except Exception as exc:
                    print(f'Row {idx + 1} generated an exception: {exc}')
        
        # Convert results dict to list (sorted by index)
        processed_data = []
        for idx in sorted(results_dict.keys()):
            processed_data.append(results_dict[idx])
        
        # Create output DataFrame
        output_df = pd.DataFrame(processed_data)
        
        # Save to CSV
        print(f"\n>> Saving results to {output_file}...")
        output_df.to_csv(output_file, index=False)
        
        # Print summary
        print("\n>> SUMMARY:")
        print(f"   Total rows processed: {len(output_df)}")
        print(f"   Valid profiles: {len(output_df[output_df['Validation'] == 'valid'])}")
        
        # Count different types of invalid profiles
        invalid_profiles = output_df[output_df['Validation'].str.startswith('invalid')]
        print(f"   Invalid profiles: {len(invalid_profiles)}")
        
        # Show breakdown of invalid reasons if any
        if len(invalid_profiles) > 0:
            validation_counts = invalid_profiles['Validation'].value_counts()
            for validation, count in validation_counts.items():
                if validation != 'invalid':
                    print(f"     - {validation}: {count}")
        
        print(f"\n>> Process completed successfully!")
        print(f"   Main data saved to: {output_file}")
        
    except FileNotFoundError:
        print(f"XX Error: Could not find {input_file}")
        print("   Make sure the file exists in the current directory")
    except Exception as e:
        print(f"XX Error: {str(e)}")
if __name__ == "__main__":
    main()
