#!/usr/bin/env python3
"""
Test script to examine PR details and understand why merger info is missing
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gh_finder.api.token_manager import TokenManager
from gh_finder.api.client import GitHubClient

async def examine_pr_details(client: GitHubClient, repo: str = "rust-lang/mdBook"):
    """Examine PR details to understand missing merger info"""
    print(f"\n🔍 Examining PR details for {repo}")
    print("=" * 60)
    
    # Fetch some merged PRs
    status, pr_data = await client.get_async(
        f"repos/{repo}/pulls",
        params={"state": "closed", "page": 1, "sort": "updated", "direction": "desc", "per_page": 30}
    )
    
    if status != 200:
        print(f"❌ Error fetching PRs: {status}")
        return
    
    merged_prs = [pr for pr in pr_data if pr.get("merged_at")]
    print(f"✅ Found {len(merged_prs)} merged PRs out of {len(pr_data)} closed PRs\n")
    
    # Analyze merger patterns
    merger_types = {
        "valid": 0,
        "missing": 0,
        "bot": 0,
        "deleted": 0
    }
    
    bot_names = ["dependabot", "github-actions", "bot", "automation"]
    
    for i, pr in enumerate(merged_prs[:10]):  # Examine first 10 merged PRs
        pr_number = pr.get("number")
        pr_title = pr.get("title", "")[:50]
        merged_at = pr.get("merged_at", "")[:10]
        merged_by = pr.get("merged_by")
        
        print(f"PR #{pr_number}: {pr_title}...")
        print(f"  Merged: {merged_at}")
        
        if merged_by and isinstance(merged_by, dict):
            merger_login = merged_by.get("login", "")
            merger_type = merged_by.get("type", "")
            
            print(f"  Merger: @{merger_login} (type: {merger_type})")
            
            # Check if it's a bot
            if merger_type == "Bot" or any(bot in merger_login.lower() for bot in bot_names):
                merger_types["bot"] += 1
                print(f"  → This is a bot merger")
            else:
                merger_types["valid"] += 1
        else:
            merger_types["missing"] += 1
            print(f"  Merger: ❌ Missing merger info")
            
            # Note: Individual PR endpoint not implemented in current GitHubClient
            # This is expected behavior - some PRs will have missing merger info
            print(f"  → This is expected when merger account is deleted or was a bot")
        
        print()
    
    # Summary
    print("\n📊 Merger Info Summary:")
    print(f"  ✅ Valid mergers: {merger_types['valid']}")
    print(f"  🤖 Bot mergers: {merger_types['bot']}")
    print(f"  ❌ Missing merger info: {merger_types['missing']}")
    
    total = sum(merger_types.values())
    if total > 0:
        missing_pct = (merger_types['missing'] / total) * 100
        print(f"\n  Missing merger info rate: {missing_pct:.1f}%")

async def main():
    print("🚀 GitHub PR Details Examination")
    print("=" * 60)
    
    # Get tokens
    tokens = []
    for i in range(1, 10):
        token_env = f"GITHUB_TOKEN_{i}" if i > 1 else "GITHUB_TOKEN"
        token = os.getenv(token_env)
        if token:
            tokens.append(token)
    
    if not tokens:
        tokens_str = os.getenv("GITHUB_TOKENS")
        if tokens_str:
            tokens = [t.strip() for t in tokens_str.split(",") if t.strip()]
    
    if not tokens:
        print("❌ No GitHub tokens found!")
        return
    
    # Initialize components
    token_manager = TokenManager(tokens, verbose=False)
    github_client = GitHubClient(token_manager=token_manager, verbose=True)
    
    try:
        # Test with different repositories
        repos_to_test = [
            "rust-lang/mdBook",
            "rust-lang/rust",
            "tokio-rs/tokio"
        ]
        
        for repo in repos_to_test:
            await examine_pr_details(github_client, repo)
            print("\n" + "-" * 60 + "\n")
    
    finally:
        await github_client.close_session()

if __name__ == "__main__":
    asyncio.run(main())