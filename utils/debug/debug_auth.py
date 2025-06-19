#!/usr/bin/env python3
"""Debug authentication differences between direct API and PyGithub"""

import os
import requests
import dotenv
from github import Github
from datetime import datetime

# Load environment variables from .env file
dotenv.load_dotenv()

# Get first token
tokens_str = os.getenv('GITHUB_TOKENS', '')
if not tokens_str:
    print("No tokens found")
    exit(1)

token = tokens_str.split(',')[0].strip()
print(f"Testing with token: {token[:8]}...\n")

# Method 1: Direct API call (like check_rate_limit.py)
print("METHOD 1: Direct API Call")
print("-" * 40)
headers = {'Authorization': f'token {token}'}
response = requests.get('https://api.github.com/rate_limit', headers=headers)

if response.status_code == 200:
    data = response.json()
    core = data['resources']['core']
    print(f"✅ Status: {response.status_code}")
    print(f"Remaining: {core['remaining']}/{core['limit']}")
    print(f"Reset: {datetime.fromtimestamp(core['reset'])}")
else:
    print(f"❌ Status: {response.status_code}")
    print(f"Response: {response.text}")

# Method 2: PyGithub
print("\n\nMETHOD 2: PyGithub")
print("-" * 40)
try:
    # Create Github instance
    g = Github(token)
    
    # Get rate limit
    rate_limit = g.get_rate_limit()
    core = rate_limit.core
    
    print(f"✅ PyGithub successful")
    print(f"Remaining: {core.remaining}/{core.limit}")
    print(f"Reset: {core.reset}")
    print(f"Used: {core.used}")
    
    # Try to get the authenticated user to verify auth
    try:
        user = g.get_user()
        print(f"Authenticated as: {user.login}")
    except Exception as e:
        print(f"Could not get authenticated user: {e}")
    
except Exception as e:
    print(f"❌ PyGithub error: {type(e).__name__}: {e}")

# Method 3: PyGithub with auth parameter
print("\n\nMETHOD 3: PyGithub with auth=")
print("-" * 40)
try:
    from github import Auth
    
    # Create auth object
    auth = Auth.Token(token)
    g = Github(auth=auth)
    
    # Get rate limit
    rate_limit = g.get_rate_limit()
    core = rate_limit.core
    
    print(f"✅ PyGithub with Auth successful")
    print(f"Remaining: {core.remaining}/{core.limit}")
    print(f"Reset: {core.reset}")
    
except Exception as e:
    print(f"❌ PyGithub with Auth error: {type(e).__name__}: {e}") 