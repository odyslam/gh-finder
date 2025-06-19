#!/usr/bin/env python3
"""
Test script to verify PR analysis is working correctly
"""

import asyncio
import os
import sys
import pytest

from test_helpers import (
    print_test_header, 
    print_test_section, 
    print_test_result, 
    check_rate_limit,
    TEST_REPOS
)

from gh_finder.api.token_manager import TokenManager
from gh_finder.api.client import GitHubClient

@pytest.mark.asyncio
async def test_pr_fetching(github_client, repo: str = "rust-lang/mdBook"):
    """Test fetching PRs from a repository"""
    print_test_section(f"Testing PR fetching for {repo}")
    
    # Test fetching closed PRs
    print("\n📋 Fetching closed PRs...")
    status, pr_data = await github_client.get_async(
        f"repos/{repo}/pulls",
        params={"state": "closed", "page": 1, "sort": "updated", "direction": "desc"}
    )
    
    assert status == 200, f"Error fetching PRs: {status} - {pr_data}"
    print(f"✅ Fetched {len(pr_data)} PRs from page 1")
    
    # Analyze the PRs
    merged_count = 0
    closed_count = 0
    mergers = {}
    
    for pr in pr_data[:20]:  # Analyze first 20
        if pr.get("merged_at"):
            merged_count += 1
            merger = pr.get("merged_by", {})
            if merger and isinstance(merger, dict):
                username = merger.get("login")
                if username:
                    mergers[username] = mergers.get(username, 0) + 1
            else:
                print(f"   ⚠️ PR #{pr.get('number')} was merged but merger info is missing")
        else:
            closed_count += 1
    
    print(f"\n📊 PR Analysis Results:")
    print(f"   - Merged PRs: {merged_count}")
    print(f"   - Closed (not merged) PRs: {closed_count}")
    print(f"   - Unique mergers found: {len(mergers)}")
    
    if mergers:
        print(f"\n👥 Top PR Mergers:")
        for username, count in sorted(mergers.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   - @{username}: {count} PRs")
    
    # Show a sample PR to verify data structure
    if pr_data:
        sample_pr = pr_data[0]
        print(f"\n🔍 Sample PR data structure:")
        print(f"   - Number: #{sample_pr.get('number')}")
        print(f"   - Title: {sample_pr.get('title', '')[:50]}...")
        print(f"   - State: {sample_pr.get('state')}")
        print(f"   - Created: {sample_pr.get('created_at')}")
        print(f"   - Merged: {sample_pr.get('merged_at', 'Not merged')}")
        print(f"   - User: @{sample_pr.get('user', {}).get('login', 'Unknown')}")
        if sample_pr.get('merged_by'):
            print(f"   - Merged by: @{sample_pr['merged_by'].get('login', 'Unknown')}")
    
    # Add assertions for a proper pytest test
    assert len(pr_data) > 0, "No PRs were fetched"
    assert merged_count + closed_count > 0, "No PRs were processed"
    
    return True

@pytest.mark.asyncio
async def test_multiple_repos(github_client):
    """Test PR fetching for multiple repositories"""
    print_test_header("Multiple Repository PR Analysis Test")
    
    # Check rate limit first
    await check_rate_limit(github_client)
    
    # Test all repositories
    for repo in TEST_REPOS:
        result = await test_pr_fetching(github_client, repo)
        assert result, f"PR fetching test failed for {repo}"
    
    print("\n✅ Test completed!")
    return True

# Command-line test runner for backward compatibility
async def main():
    """Main test function for command-line usage"""
    print_test_header("GitHub PR Analysis Test")
    
    # Get token
    tokens = []
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN_1")
    if token:
        tokens.append(token)
    
    # Also check for GITHUB_TOKENS (plural) with comma-separated tokens
    if not tokens:
        tokens_str = os.getenv("GITHUB_TOKENS")
        if tokens_str:
            tokens = [t.strip() for t in tokens_str.split(",") if t.strip()]
    
    if not tokens:
        print("❌ No GitHub token found!")
        print("   Please set GITHUB_TOKEN, GITHUB_TOKEN_1, or GITHUB_TOKENS environment variable")
        return
    
    print("✅ Found GitHub token")
    
    # Initialize client
    token_manager = TokenManager(tokens, verbose=True)
    client = GitHubClient(
        token=tokens[0],
        verbose=True,
        token_manager=token_manager,
        per_page=100
    )
    
    # Check rate limit
    await check_rate_limit(client)
    
    # Test repositories
    for repo in TEST_REPOS:
        await test_pr_fetching(client, repo)
    
    await client.close_session()
    print("\n✅ Test completed!")

if __name__ == "__main__":
    asyncio.run(main())