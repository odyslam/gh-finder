#!/usr/bin/env python3
"""Check GitHub API rate limit status for all tokens"""

import requests
import os
import sys
from datetime import datetime
import time
import dotenv

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import token loading function from gh_finder
try:
    from gh_finder.utils.config import load_env_vars, load_tokens_from_file
except ImportError:
    # Fallback to local implementation if import fails
    def load_env_vars():
        """Load GitHub tokens from environment variables"""
        # Load .env file
        dotenv.load_dotenv()
        
        tokens = []
        # Check for GITHUB_TOKENS (multiple)
        multi_tokens = os.environ.get('GITHUB_TOKENS')
        if multi_tokens:
            for token in multi_tokens.split(','):
                if token.strip() and len(token.strip()) >= 10:
                    tokens.append(token.strip())
        
        # Check for GITHUB_TOKEN (single)
        token = os.environ.get('GITHUB_TOKEN')
        if token and token.strip() and len(token.strip()) >= 10:
            if token.strip() not in tokens:
                tokens.append(token.strip())
        
        # Check for numbered tokens
        for i in range(1, 10):
            token_name = f"GITHUB_TOKEN_{i}"
            token = os.environ.get(token_name)
            if token and token.strip() and len(token.strip()) >= 10:
                if token.strip() not in tokens:
                    tokens.append(token.strip())
        
        return tokens
    
    def load_tokens_from_file(filename):
        """Load tokens from a file"""
        tokens = []
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and len(line) >= 10:
                        tokens.append(line)
            return tokens
        except Exception:
            return []

# First try to load from .env file
print("🔍 Looking for GitHub tokens...")
dotenv.load_dotenv()
tokens = load_env_vars()

# If tokens found in environment, use those
if tokens:
    print(f"✅ Found {len(tokens)} tokens from environment variables")
# Check command line arguments
elif len(sys.argv) > 1:
    # Check if argument is a file
    if os.path.isfile(sys.argv[1]):
        tokens = load_tokens_from_file(sys.argv[1])
        if tokens:
            print(f"✅ Found {len(tokens)} tokens from file {sys.argv[1]}")
        else:
            print(f"❌ No valid tokens found in file {sys.argv[1]}")
    # Could be single token or comma-separated
    elif ',' in sys.argv[1]:
        tokens = [t.strip() for t in sys.argv[1].split(',') if t.strip() and len(t.strip()) >= 10]
        print(f"✅ Found {len(tokens)} tokens from command line")
    else:
        token = sys.argv[1].strip()
        if len(token) >= 10:
            tokens = [token]
            print(f"✅ Found 1 token from command line")
        else:
            print(f"❌ Token provided is too short ({len(token)} chars, minimum 10 required)")
else:
    print("Please provide tokens via:")
    print("  - GITHUB_TOKENS env var (comma-separated)")
    print("  - GITHUB_TOKEN env var (single token)")
    print("  - Command line argument (token or path to tokens file)")
    sys.exit(1)

# Validate tokens found
if not tokens:
    print("❌ No valid tokens found. Exiting.")
    sys.exit(1)

# Check each token
print("\n" + "="*60)
print("🔍 CHECKING ALL TOKENS RATE LIMIT STATUS")
print("="*60)

all_exhausted = True
earliest_reset = None
current_time = time.time()

for i, token in enumerate(tokens):
    print(f"\nToken {i+1}: {token[:8]}...")
    
    # Make API call to check rate limit
    headers = {'Authorization': f'token {token}'}
    response = requests.get('https://api.github.com/rate_limit', headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        core = data['resources']['core']
        
        remaining = core["remaining"]
        limit = core["limit"]
        reset_timestamp = core['reset']
        
        # Check if this token has remaining calls
        if remaining > 0:
            all_exhausted = False
        
        # Track earliest reset time
        if remaining == 0 and (earliest_reset is None or reset_timestamp < earliest_reset):
            earliest_reset = reset_timestamp
        
        # Status
        percentage = (remaining / limit * 100) if limit > 0 else 0
        status_emoji = "🟢" if percentage > 50 else "🟡" if percentage > 20 else "🔴"
        
        print(f'  {status_emoji} Remaining: {remaining}/{limit} ({percentage:.1f}%)')
        print(f'  Used: {limit - remaining}')
        
        # Convert reset timestamp to readable time
        reset_time = datetime.fromtimestamp(reset_timestamp)
        
        # Calculate time difference
        time_diff = reset_timestamp - current_time
        if time_diff > 0:
            hours = int(time_diff // 3600)
            minutes = int((time_diff % 3600) // 60)
            seconds = int(time_diff % 60)
            time_str = f'{hours}h {minutes}m {seconds}s'
            print(f'  ⏰ Reset: {reset_time} ({time_str} from now)')
        else:
            print(f'  ✅ Reset time has passed! Token should be refreshed.')
            print(f'  Reset was at: {reset_time}')
            
        # Debug info
        if remaining == 0:
            print(f'  ⚠️ This token is exhausted!')
            
    else:
        print(f'  ❌ Error: {response.status_code}')
        if response.status_code == 401:
            print(f'  Invalid token or authentication failed')
        else:
            print(f'  {response.text}')

# Summary
print("\n" + "="*60)
print("SUMMARY")
print("="*60)

if all_exhausted:
    print("❌ ALL TOKENS ARE EXHAUSTED")
    if earliest_reset:
        reset_time = datetime.fromtimestamp(earliest_reset)
        time_until = earliest_reset - current_time
        if time_until > 0:
            hours = int(time_until // 3600)
            minutes = int((time_until % 3600) // 60)
            print(f"\n⏰ Earliest reset: {reset_time}")
            print(f"⏳ Time to wait: {hours}h {minutes}m")
        else:
            print(f"\n✅ Earliest reset time has passed: {reset_time}")
            print("Tokens should be refreshing soon!")
else:
    print("✅ At least one token has remaining API calls")
    
print("\n💡 GitHub rate limits reset every hour")
print("If reset time has passed but tokens still show 0, try again in a minute") 