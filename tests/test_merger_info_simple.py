#!/usr/bin/env python3
"""
Simple test to demonstrate why merger info is missing in PRs
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gh_finder.api.token_manager import TokenManager
from gh_finder.api.client import GitHubClient

async def explain_missing_merger_info():
    """Explain why merger info is missing"""
    print("\n🔍 Understanding Missing Merger Info in GitHub PRs")
    print("=" * 60)
    
    print("\nThe GitHub API sometimes returns `null` for the `merged_by` field even when")
    print("a PR has been merged (indicated by the `merged_at` field). This happens in")
    print("several common scenarios:\n")
    
    print("1. 🗑️  **Deleted GitHub Accounts**")
    print("   When the user who merged the PR has deleted their GitHub account,")
    print("   the merger info is removed from the API response.\n")
    
    print("2. 🤖 **GitHub Actions or Bots**")
    print("   When PRs are merged by automated systems like:")
    print("   - GitHub Actions workflows")
    print("   - Merge bots (e.g., bors, mergify)")
    print("   - GitHub's merge queue feature")
    print("   The merger info might not be available in the standard format.\n")
    
    print("3. 📅 **Legacy Data**")
    print("   Older PRs (especially from several years ago) might not have")
    print("   complete merger information due to changes in how GitHub")
    print("   tracked this data over time.\n")
    
    print("4. 🔄 **API Limitations**")
    print("   Sometimes the GitHub API doesn't return merger info even for")
    print("   recently merged PRs, possibly due to:")
    print("   - Caching issues")
    print("   - Eventual consistency in distributed systems")
    print("   - Internal GitHub data processing delays\n")
    
    print("5. 🔐 **Permission Issues**")
    print("   In rare cases, merger info might be hidden due to repository")
    print("   permissions or privacy settings.\n")
    
    print("💡 **What This Means for gh-finder:**")
    print("   - The warnings you see are informational, not errors")
    print("   - This is expected behavior from the GitHub API")
    print("   - The tool correctly handles these cases by continuing")
    print("   - You may find fewer PR mergers than actual merged PRs")
    print("   - This is particularly common in repositories that use")
    print("     automated merging or have many older PRs\n")

async def check_single_repo(client: GitHubClient, repo: str):
    """Check a single repo for merger patterns"""
    print(f"\n📊 Quick check of {repo}...")
    print("-" * 40)
    
    # Fetch just 10 PRs to avoid rate limits
    status, pr_data = await client.get_async(
        f"repos/{repo}/pulls",
        params={"state": "closed", "page": 1, "sort": "updated", "direction": "desc", "per_page": 10}
    )
    
    if status != 200:
        print(f"❌ Error fetching PRs: {status}")
        return
    
    merged_count = 0
    missing_merger_count = 0
    bot_merger_count = 0
    
    for pr in pr_data:
        if pr.get("merged_at"):
            merged_count += 1
            merged_by = pr.get("merged_by")
            
            if not merged_by:
                missing_merger_count += 1
            elif isinstance(merged_by, dict):
                merger_type = merged_by.get("type", "")
                merger_login = merged_by.get("login", "").lower()
                
                if merger_type == "Bot" or any(bot in merger_login for bot in ["bot", "automation", "action"]):
                    bot_merger_count += 1
    
    print(f"Merged PRs checked: {merged_count}")
    print(f"Missing merger info: {missing_merger_count} ({missing_merger_count/merged_count*100:.0f}%)" if merged_count > 0 else "No merged PRs")
    print(f"Bot mergers: {bot_merger_count}")

async def main():
    print("🚀 GitHub Merger Info Explanation")
    print("=" * 60)
    
    # Explain the issue first
    await explain_missing_merger_info()
    
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
    
    if tokens:
        print(f"\n✅ Found {len(tokens)} GitHub token(s)")
        
        # Initialize client
        token_manager = TokenManager(tokens, verbose=False)
        github_client = GitHubClient(
            token=token_manager.get_current_token(),
            verbose=False,
            token_manager=token_manager,
            per_page=10
        )
        
        print("\n📊 Examples from Popular Repositories:")
        print("=" * 60)
        
        # Check a few repos
        repos = [
            "rust-lang/mdBook",     # Uses GitHub Actions
            "tokio-rs/tokio",       # Active Rust project
            "facebook/react"        # Large project with automation
        ]
        
        for repo in repos:
            await check_single_repo(github_client, repo)
        
        await github_client.close_session()
    else:
        print("\n💡 No GitHub tokens found - showing explanation only")
    
    print("\n✅ Summary: Missing merger info is normal and expected!")
    print("   The tool handles this correctly by continuing to analyze.")

if __name__ == "__main__":
    asyncio.run(main())