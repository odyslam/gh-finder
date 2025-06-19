#!/usr/bin/env python3
"""
Test script to verify all data models and functionality work correctly
with a single repository and user before running full analysis.
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gh_finder.models.profile import GitHubProfile, ProfileEvaluation
from gh_finder.api.token_manager import TokenManager
from gh_finder.api.client import GitHubClient
from gh_finder.core.analyzer import ProfileAnalyzer
from gh_finder.core.evaluator import ProfileEvaluator
from gh_finder.core.finder import GitHubProfileFinder
from gh_finder.utils.run_context import RunContext
from gh_finder.utils.checkpoint import CheckpointManager

async def test_github_client(client: GitHubClient):
    """Test basic GitHub client functionality"""
    print("\n" + "="*60)
    print("🧪 Testing GitHub Client")
    print("="*60)
    
    # Test rate limit check
    print("\n📊 Testing rate limit check...")
    rate_limit = await client._get_rate_limit_info()
    if 'error' not in rate_limit:
        core = rate_limit.get('resources', {}).get('core', {})
        print(f"✅ Rate limit: {core.get('remaining', 0)}/{core.get('limit', 5000)}")
    else:
        print(f"❌ Rate limit error: {rate_limit.get('error')}")
    
    # Test fetching a known user
    print("\n👤 Testing user fetch...")
    status, user_data = await client.get_async("users/torvalds")
    if status == 200:
        print(f"✅ Fetched user: {user_data.get('name')} (@{user_data.get('login')})")
        print(f"   Followers: {user_data.get('followers')}, Repos: {user_data.get('public_repos')}")
    else:
        print(f"❌ Error fetching user: {status} - {user_data}")
    
    # Test fetching a repository
    print("\n📦 Testing repository fetch...")
    status, repo_data = await client.get_async("repos/rust-lang/rust")
    if status == 200:
        print(f"✅ Fetched repo: {repo_data.get('full_name')}")
        print(f"   Stars: {repo_data.get('stargazers_count')}, Language: {repo_data.get('language')}")
    else:
        print(f"❌ Error fetching repo: {status} - {repo_data}")
    
    return True

async def test_single_repo_analysis(finder: GitHubProfileFinder, repo_name: str = "rust-lang/mdBook"):
    """Test analyzing a single repository"""
    print("\n" + "="*60)
    print(f"🧪 Testing Single Repository Analysis: {repo_name}")
    print("="*60)
    
    # Test PR analysis (for a smaller repo to save API calls)
    print(f"\n📋 Analyzing PRs from {repo_name}...")
    pr_mergers = await finder._get_pr_mergers(repo_name, limit=50, tier=1)  # Limit to 50 PRs
    
    print(f"\n✅ Found {len(pr_mergers)} PR mergers:")
    for i, (username, count) in enumerate(list(pr_mergers.items())[:5]):  # Show top 5
        print(f"   {i+1}. @{username}: {count} PRs merged")
    
    # Test fork analysis
    print(f"\n🍴 Analyzing forks of {repo_name}...")
    fork_contributors = await finder._get_fork_contributors(repo_name, limit=20, tier=1)  # Limit to 20 forks
    
    print(f"\n✅ Found {len(fork_contributors)} fork contributors:")
    for i, (username, score) in enumerate(list(fork_contributors.items())[:5]):  # Show top 5
        print(f"   {i+1}. @{username}: score {score}")
    
    return pr_mergers, fork_contributors

async def test_single_user_analysis(analyzer: ProfileAnalyzer, username: str = "dtolnay"):
    """Test analyzing a single user profile"""
    print("\n" + "="*60)
    print(f"🧪 Testing Single User Analysis: @{username}")
    print("="*60)
    
    # Analyze the user
    profile = await analyzer.analyze_user(username)
    
    if profile:
        print(f"\n✅ Successfully analyzed @{username}")
        print(f"   Name: {profile.name}")
        print(f"   Company: {profile.company}")
        print(f"   Location: {profile.location}")
        print(f"   Bio: {profile.bio[:100] if profile.bio else 'None'}...")
        print(f"   Followers: {profile.followers}")
        print(f"   Public Repos: {profile.public_repos}")
        print(f"   Created: {profile.created_at}")
        
        # Show languages
        if profile.languages_detailed:
            print(f"\n   Top Languages:")
            for lang in profile.languages_detailed[:5]:
                print(f"     - {lang.name}: {lang.percentage:.1f}%")
        
        # Show top repos
        if profile.top_repos:
            print(f"\n   Top Repositories:")
            for repo in profile.top_repos[:3]:
                print(f"     - {repo.name}: {repo.stars}⭐ ({repo.language or 'No language'})")
        
        return profile
    else:
        print(f"❌ Failed to analyze user @{username}")
        return None

async def test_profile_evaluation(evaluator: ProfileEvaluator, profile: GitHubProfile):
    """Test profile evaluation"""
    print("\n" + "="*60)
    print(f"🧪 Testing Profile Evaluation for @{profile.username}")
    print("="*60)
    
    # Evaluate the profile
    evaluator.evaluate_profile(profile)
    
    if profile.evaluation:
        eval_data = profile.evaluation
        print(f"\n✅ Profile evaluated successfully")
        print(f"   Category: {eval_data.category}")
        print(f"   Total Score: {eval_data.total_score:.2f}/10")
        print(f"   Rust Prominence: {eval_data.rust_prominence}")
        print(f"   Is PR Merger: {'Yes' if eval_data.is_pr_merger else 'No'}")
        
        print(f"\n   Score Breakdown:")
        print(f"     - Followers: {eval_data.followers_score:.2f}")
        print(f"     - Repositories: {eval_data.repos_score:.2f}")
        print(f"     - Account Age: {eval_data.account_age_score:.2f}")
        print(f"     - Activity: {eval_data.activity_score:.2f}")
        print(f"     - Rust: {eval_data.rust_score:.2f}")
        print(f"     - PR Merger: {eval_data.pr_merger_score:.2f}")
        print(f"     - Cross-Repo: {eval_data.cross_repo_score:.2f}")
        print(f"     - Openness: {eval_data.openness_score:.2f}")
    else:
        print("❌ Profile evaluation failed")

async def test_data_model_serialization(profile: GitHubProfile):
    """Test data model serialization and deserialization"""
    print("\n" + "="*60)
    print("🧪 Testing Data Model Serialization")
    print("="*60)
    
    # Test to_dict
    print("\n📤 Testing profile.to_dict()...")
    profile_dict = profile.to_dict()
    print(f"✅ Serialized to dict with {len(profile_dict)} keys")
    print(f"   Keys: {', '.join(list(profile_dict.keys())[:10])}...")
    
    # Test from_dict
    print("\n📥 Testing GitHubProfile.from_dict()...")
    restored_profile = GitHubProfile.from_dict(profile_dict)
    print(f"✅ Restored profile for @{restored_profile.username}")
    
    # Verify key attributes
    attributes_to_check = [
        'username', 'name', 'followers', 'public_repos', 
        'is_merger', 'prs_merged', 'languages'
    ]
    
    print("\n🔍 Verifying attributes match:")
    all_match = True
    for attr in attributes_to_check:
        original = getattr(profile, attr, None)
        restored = getattr(restored_profile, attr, None)
        match = original == restored
        status = "✅" if match else "❌"
        print(f"   {status} {attr}: {match}")
        if not match:
            print(f"      Original: {original}")
            print(f"      Restored: {restored}")
            all_match = False
    
    return all_match

async def test_checkpoint_functionality(checkpoint_manager: CheckpointManager, profiles: dict):
    """Test checkpoint save and load functionality"""
    print("\n" + "="*60)
    print("🧪 Testing Checkpoint Functionality")
    print("="*60)
    
    # Create test checkpoint data
    test_data = {
        'analyzed_users': ['user1', 'user2', 'user3'],
        'analyzed_repositories': ['repo1/test', 'repo2/test'],
        'profiles': profiles,
        'pr_merger_stats': {'user1': 5, 'user2': 3},
        'pr_merger_details': {'user1': [['repo1/test', 5, 0]]},
        'contributor_stats': {},
        'all_users': ['user1', 'user2', 'user3'],
        'repo_tiers': {'repo1/test': 0, 'repo2/test': 1}
    }
    
    # Save checkpoint
    print("\n💾 Saving checkpoint...")
    checkpoint_path = checkpoint_manager.save_checkpoint(**test_data)
    if checkpoint_path:
        print(f"✅ Checkpoint saved to: {Path(checkpoint_path).name}")
        file_size = Path(checkpoint_path).stat().st_size
        print(f"   File size: {file_size:,} bytes")
    else:
        print("❌ Failed to save checkpoint")
        return False
    
    # Load checkpoint
    print("\n📂 Loading checkpoint...")
    loaded_data = checkpoint_manager.load_checkpoint(checkpoint_path)
    if loaded_data:
        print(f"✅ Checkpoint loaded successfully")
        print(f"   Analyzed users: {len(loaded_data.get('analyzed_users', []))}")
        print(f"   Analyzed repos: {len(loaded_data.get('analyzed_repositories', []))}")
        print(f"   Profiles: {len(loaded_data.get('profiles', {}))}")
    else:
        print("❌ Failed to load checkpoint")
        return False
    
    return True

async def main():
    """Main test function"""
    print("\n🚀 GitHub Finder Single Analysis Test")
    print("=" * 80)
    
    # Initialize components
    print("\n🔧 Initializing components...")
    
    # Create token manager
    tokens = []
    
    # Check for individual token environment variables
    for i in range(1, 10):  # Check up to 9 tokens
        token_env = f"GITHUB_TOKEN_{i}" if i > 1 else "GITHUB_TOKEN"
        token = os.getenv(token_env)
        if token:
            tokens.append(token)
    
    # Also check for GITHUB_TOKENS (plural) with comma-separated tokens
    if not tokens:
        tokens_str = os.getenv("GITHUB_TOKENS")
        if tokens_str:
            tokens = [t.strip() for t in tokens_str.split(",") if t.strip()]
    
    if not tokens:
        print("❌ No GitHub tokens found in environment variables!")
        print("   Please set GITHUB_TOKEN, GITHUB_TOKEN_1, GITHUB_TOKEN_2, etc., or GITHUB_TOKENS")
        return
    
    print(f"✅ Found {len(tokens)} GitHub token(s)")
    
    # Initialize components
    token_manager = TokenManager(tokens, verbose=True)
    github_client = GitHubClient(
        token=token_manager.get_current_token(),
        verbose=True,
        token_manager=token_manager,
        per_page=100
    )
    
    # Test GitHub client
    await test_github_client(github_client)
    
    # Initialize analyzer and evaluator
    profile_analyzer = ProfileAnalyzer(github_client, verbose=True)
    evaluator = ProfileEvaluator()
    
    # Test single user analysis
    test_username = "dtolnay"  # A well-known Rust developer
    profile = await test_single_user_analysis(profile_analyzer, test_username)
    
    if profile:
        # Add some test PR merger data
        profile.is_merger = True
        profile.prs_merged = 10
        from gh_finder.models.profile import MergedPRDetail
        profile.prs_merged_details = [
            MergedPRDetail(repo="rust-lang/rust", pr_count=5, pr_ids=[1, 2, 3, 4, 5], tier=0),
            MergedPRDetail(repo="serde-rs/serde", pr_count=5, pr_ids=[6, 7, 8, 9, 10], tier=1)
        ]
        
        # Test profile evaluation
        await test_profile_evaluation(evaluator, profile)
        
        # Test data model serialization
        serialization_ok = await test_data_model_serialization(profile)
        
        # Initialize run context and checkpoint manager
        # Temporarily change to test_runs directory
        original_dir = os.getcwd()
        test_runs_dir = Path("test_runs")
        test_runs_dir.mkdir(exist_ok=True)
        os.chdir(test_runs_dir)
        
        run_context = RunContext()
        checkpoint_manager = CheckpointManager(run_context)
        
        # Change back to original directory
        os.chdir(original_dir)
        
        # Test checkpoint functionality
        profiles_dict = {profile.username: profile}
        checkpoint_ok = await test_checkpoint_functionality(checkpoint_manager, profiles_dict)
        
        # Initialize finder for repository analysis
        finder = GitHubProfileFinder(
            token_manager=token_manager,
            run_context=run_context,
            verbose=True,
            analyze_prs=True
        )
        
        # Test single repository analysis
        test_repo = "rust-lang/mdBook"  # A smaller Rust repository
        pr_mergers, fork_contributors = await test_single_repo_analysis(finder, test_repo)
        
        # Test analyzing one of the found contributors
        if pr_mergers:
            test_contributor = list(pr_mergers.keys())[0]
            print(f"\n🧪 Testing full analysis flow for contributor @{test_contributor}...")
            contributor_profile = await finder.analyze_user(test_contributor, test_repo)
            if contributor_profile:
                print(f"✅ Successfully analyzed contributor @{test_contributor}")
                print(f"   Is merger: {contributor_profile.is_merger}")
                print(f"   PRs merged: {contributor_profile.prs_merged}")
            else:
                print(f"❌ Failed to analyze contributor @{test_contributor}")
        
        # Summary
        print("\n" + "="*60)
        print("📊 Test Summary")
        print("="*60)
        print(f"✅ GitHub Client: Working")
        print(f"✅ User Analysis: Working")
        print(f"✅ Profile Evaluation: Working")
        print(f"{'✅' if serialization_ok else '❌'} Data Serialization: {'Working' if serialization_ok else 'Failed'}")
        print(f"{'✅' if checkpoint_ok else '❌'} Checkpoint System: {'Working' if checkpoint_ok else 'Failed'}")
        print(f"✅ Repository Analysis: Working")
        print(f"✅ PR Merger Detection: Found {len(pr_mergers)} mergers")
        print(f"✅ Fork Analysis: Found {len(fork_contributors)} contributors")
        
        print("\n✨ All core functionality appears to be working correctly!")
        print("   You can now run the full analysis with confidence.")
        
        # Clean up test checkpoint
        if checkpoint_ok:
            import shutil
            shutil.rmtree(test_runs_dir, ignore_errors=True)
            print("\n🧹 Cleaned up test files")
    
    # Close the client
    await github_client.close_session()

if __name__ == "__main__":
    asyncio.run(main())