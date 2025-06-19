#!/usr/bin/env python3
"""Debug what PyGithub is returning for rate limits"""

import os
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

# Create Github instance
g = Github(token)

# Get rate limit object
print("Getting rate limit from PyGithub...")
rate_limit_obj = g.get_rate_limit()

# Check the actual object
print(f"\nRate limit object type: {type(rate_limit_obj)}")
print(f"Rate limit object: {rate_limit_obj}")

# Check core limits
core = rate_limit_obj.core
print(f"\nCore rate limit:")
print(f"  Type: {type(core)}")
print(f"  Limit: {core.limit}")
print(f"  Remaining: {core.remaining}")
print(f"  Used: {core.used}")
print(f"  Reset: {core.reset}")
print(f"  Reset type: {type(core.reset)}")
print(f"  Reset timestamp: {core.reset.timestamp()}")

# Check if we have _rawData
if hasattr(rate_limit_obj, '_rawData'):
    print(f"\n_rawData exists: {rate_limit_obj._rawData}")
else:
    print("\n_rawData does NOT exist")

# Try to check headers
print("\nChecking if we can see the last response headers...")
if hasattr(g, '_Github__requester'):
    requester = g._Github__requester
    if hasattr(requester, '_Requester__connection'):
        print("  Found connection object")
        if hasattr(requester._Requester__connection, 'headers'):
            print(f"  Headers: {requester._Requester__connection.headers}")
    else:
        print("  No connection object found")

# Make another call and check what happens
print("\n\nMaking a test API call to /user...")
try:
    user = g.get_user()
    print(f"✅ Got user: {user.login}")
    
    # Check rate limit again
    rate_limit_obj2 = g.get_rate_limit()
    print(f"\nAfter API call:")
    print(f"  Remaining: {rate_limit_obj2.core.remaining}")
    print(f"  Used: {rate_limit_obj2.core.used}")
except Exception as e:
    print(f"❌ Error: {e}") 