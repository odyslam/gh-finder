#!/usr/bin/env python3
"""Test rate limit conversion"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from github import Github
from gh_finder.api.client import GitHubClient

# Get first token
tokens_str = os.getenv('GITHUB_TOKENS', '')
token = tokens_str.split(',')[0].strip()

# Test direct PyGithub
print("1. Direct PyGithub test:")
g = Github(token)
rate_limit = g.get_rate_limit()
print(f"   Remaining: {rate_limit.core.remaining}")
print(f"   Reset: {rate_limit.core.reset}")
print(f"   Reset timestamp: {rate_limit.core.reset.timestamp()}")

# Test our client conversion
print("\n2. Testing our _convert_pygithub_object_to_dict:")
client = GitHubClient(token=token, verbose=False)
converted = client._convert_pygithub_object_to_dict(rate_limit)
print(f"   Converted: {converted}")

# Check the specific values
core = converted.get('resources', {}).get('core', {})
print(f"\n3. Extracted core values:")
print(f"   Remaining: {core.get('remaining', 'NOT FOUND')}")
print(f"   Limit: {core.get('limit', 'NOT FOUND')}")
print(f"   Reset: {core.get('reset', 'NOT FOUND')}")

# Test with a fresh rate limit check
print("\n4. Testing get_rate_limit through get_async:")
import asyncio

async def test_get_async():
    client = GitHubClient(token=token, verbose=True)
    code, data = await client.get_async("rate_limit")
    print(f"   Response code: {code}")
    print(f"   Data: {data}")
    if code == 200:
        core = data.get('resources', {}).get('core', {})
        print(f"   Core remaining: {core.get('remaining', 'NOT FOUND')}")
        print(f"   Core reset: {core.get('reset', 'NOT FOUND')}")

asyncio.run(test_get_async()) 