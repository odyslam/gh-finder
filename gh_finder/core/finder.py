"""
GitHub profile finder for identifying promising developers
"""

import asyncio
import copy
import json
import os
import re
import sys
import traceback
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set, Tuple, Union, Callable, Awaitable
from pathlib import Path

from tqdm import tqdm

from ..api.client import GitHubClient, GitHubRateLimitError, GitHubAuthError
from ..api.token_manager import TokenManager
from ..core.analyzer import ProfileAnalyzer
from ..core.evaluator import ProfileEvaluator
from ..models.profile import GitHubProfile, CrossRepoDetail, MergedPRDetail
from ..utils.run_context import RunContext
from ..utils.checkpoint import CheckpointManager
from ..utils.ai_prompt_generator import generate_ai_prompt as generate_prompt

class GitHubProfileFinder:
    """Finds promising developers on GitHub based on repository activity"""
    
    def __init__(self, 
                 token_manager: TokenManager,
                 run_context: Optional[RunContext] = None,
                 verbose: bool = False,
                 max_concurrent: int = 5,
                 config: Optional[Dict] = None,
                 rate_limit_threshold: int = 200,
                 checkpoint_file: Optional[str] = None,
                 analyze_prs: bool = False,
                 force_reanalyze: bool = False,
                 github_client_per_page: int = 100):
        """Initialize the GitHub profile finder
        
        Args:
            token_manager: TokenManager instance for API authentication
            run_context: Optional RunContext for logging
            verbose: Enable verbose output
            max_concurrent: Maximum concurrent async tasks running PyGithub calls
            config: Optional configuration dictionary
            rate_limit_threshold: Threshold for TokenManager (if it still uses this concept)
            checkpoint_file: Optional checkpoint file to resume from
            analyze_prs: Whether to analyze PRs (can exceed API rate limits)
            force_reanalyze: Whether to force reanalysis even when resuming from checkpoint
            github_client_per_page: Default items per page for the GitHubClient
        """
        self.token_manager = token_manager
        self.verbose = verbose
        self.analyze_prs = analyze_prs
        self.run_context = run_context
        self.config = config or {}
        self.rate_limit_threshold = rate_limit_threshold
        
        self.github = GitHubClient(
            token_manager=self.token_manager, 
            verbose=verbose, 
            per_page=github_client_per_page
        )
        self.github.update_concurrency_limit(max_concurrent)
        
        self.profile_analyzer = ProfileAnalyzer(
            github_client=self.github,
            verbose=verbose
        )
        self.evaluator = ProfileEvaluator(verbose)
        
        self.profiles: Dict[str, GitHubProfile] = {}
        self.pr_merger_stats = defaultdict(int)
        self.pr_merger_details: Dict[str, List[Tuple[str, int, int]]] = defaultdict(list)
        self.contributor_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.analyzed_repositories: Set[str] = set()
        self.checkpoint_manager = CheckpointManager(run_context)
        self.analyzed_users: Set[str] = set()
        
        # Track repository tiers
        self.repo_tiers: Dict[str, int] = {}  # Map repo_name -> tier
        
        if checkpoint_file:
            self._load_from_checkpoint(checkpoint_file, force_reanalyze)
        
    def _load_from_checkpoint(self, checkpoint_file: str, force_reanalyze: bool = False) -> None:
        checkpoint_data = self.checkpoint_manager.load_checkpoint(checkpoint_file)
        if not checkpoint_data:
            print("❌ Failed to load checkpoint, starting fresh")
            return
        try:
            if self.verbose:
                print(f"📝 Found in checkpoint: ...") # Simplified for brevity
            
            self.analyzed_users = set(checkpoint_data.get("analyzed_users", []))
            
            if force_reanalyze:
                print("🔄 Force reanalysis enabled - will reanalyze all repositories and users")
                self.analyzed_repositories = set()
            else:
                analyzed_repos_set = set()
                for repo_item in checkpoint_data.get("analyzed_repositories", []):
                    if isinstance(repo_item, str): analyzed_repos_set.add(repo_item)
                    # Assuming checkpoint stores repo names as strings now for simplicity with PyGithub
                self.analyzed_repositories = analyzed_repos_set
                print(f"📊 Loaded {len(self.analyzed_repositories)} previously analyzed repositories from checkpoint")
            
            profile_dicts = checkpoint_data.get("profiles", {})
            self.profiles = {}
            for username, profile_dict in profile_dicts.items():
                try:
                    if not profile_dict or not isinstance(profile_dict, dict): continue
                    profile = GitHubProfile.from_dict(profile_dict)
                    
                    # Skip minimal profiles when loading from checkpoint
                    if (profile.created_at is None and 
                        profile.followers == 0 and 
                        profile.public_repos == 0 and
                        profile.bio is None and
                        profile.name is None):
                        if self.verbose:
                            print(f"  ⚠️ Skipping minimal profile for {username} from checkpoint")
                        continue
                    
                    self.profiles[username] = profile
                except Exception as e_profile:
                    print(f"⚠️ Warning: Could not load profile for {username}: {str(e_profile)}")
                    continue
            
            all_users_ckp = set(checkpoint_data.get("all_users", []))
            remaining_users_ckp = set(checkpoint_data.get("remaining_users", []))
            
            print(f"📊 Loaded {len(self.profiles)} profiles, {len(self.analyzed_users)} analyzed users")
            print(f"📊 Total users from ckp: {len(all_users_ckp)}, Remaining from ckp: {len(remaining_users_ckp)}")
            
            # Simplified cleanup and default init logic from original, assuming from_dict handles it mostly
            cleaned_count = 0
            for profile in self.profiles.values():
                # Ensure essential lists exist (GitHubProfile.from_dict should handle defaults)
                if not hasattr(profile, 'languages'): profile.languages = []
                if not hasattr(profile, 'top_repos'): profile.top_repos = []
                # ... other similar checks from original ...

            # Load PR merger stats & details (simplified)
            self.pr_merger_stats = defaultdict(int, checkpoint_data.get("pr_merger_stats", {}))
            self.pr_merger_details = defaultdict(list)
            for uname, details_list in checkpoint_data.get("pr_merger_details", {}).items():
                 self.pr_merger_details[uname] = [tuple(d) for d in details_list if isinstance(d, list) and len(d) == 3]

            self.contributor_stats = defaultdict(lambda: defaultdict(int))
            loaded_contrib_stats = checkpoint_data.get("contributor_stats", {})
            for user, repo_counts in loaded_contrib_stats.items():
                self.contributor_stats[user] = defaultdict(int, repo_counts)

            # Load repo tiers from checkpoint if available
            self.repo_tiers = checkpoint_data.get("repo_tiers", {})
            
            print(f"✅ Restored state from checkpoint")
        except Exception as e:
            print(f"❌ Error loading checkpoint: {str(e)}")
            if self.verbose: traceback.print_exc()
            self._reset_state_to_fresh()

    def _reset_state_to_fresh(self):
        print("🔄 Resetting to fresh state.")
        self.analyzed_users = set()
        self.analyzed_repositories = set()
        self.profiles = {}
        self.pr_merger_stats = defaultdict(int)
        self.pr_merger_details = defaultdict(list)
        self.contributor_stats = defaultdict(lambda: defaultdict(int))
            
    async def analyze_repository(self, repo_name: str, limit: int = 0, tier: int = 99) -> List[str]:
        """Analyze a GitHub repository for promising contributors. `limit` is less effective with PyGithub page-based fetching."""
        repo_name_str = self._validate_repo_name(repo_name)
        if not repo_name_str:
            print(f"⚠️ Invalid repository name format: {repo_name}")
            return []
        
        print(f"\n⏳ Analyzing repository: {repo_name_str} (Tier {tier})")
        
        # Store the tier for this repository
        self.repo_tiers[repo_name_str] = tier
        
        try:
            users_found: Dict[str, int] = {}
            
            # Hybrid approach: Use PR analysis for high-priority repos (Tier 0-1)
            # and fork analysis for lower priority repos to conserve API calls
            if tier <= 1 and self.analyze_prs:
                print(f"👥 Finding contributors using PR analysis for {repo_name_str} (High-priority Tier {tier})")
                # Apply a reasonable limit for PR analysis to avoid analyzing thousands of PRs
                pr_limit = limit if limit > 0 else 500  # Default to 500 PRs for tier 0-1 if no limit specified
                users_found = await self._get_pr_mergers(repo_name_str, limit=pr_limit, tier=tier)
            else:
                # Use fork analysis for lower tiers or when PR analysis is disabled
                if tier <= 1 and not self.analyze_prs:
                    print(f"ℹ️ Tier {tier} repo but PR analysis disabled, using fork analysis")
                print(f"👥 Finding contributors using fork analysis for {repo_name_str} (API-friendlier)")
                # Apply progressive limits based on tier
                fork_limit = self._calculate_progressive_limit(limit, tier)
                users_found = await self._get_fork_contributors(repo_name_str, limit=fork_limit, tier=tier)
                
            print(f"✅ Found {len(users_found)} potential contributors in {repo_name_str}")
            return list(users_found.keys())
        except GitHubRateLimitError:
            print(f"❌ Rate limit exceeded while analyzing {repo_name_str}")
            raise
        except GitHubAuthError:
            print(f"🔒 Auth error while analyzing {repo_name_str}")
            raise
        except Exception as e:
            print(f"❌ Unexpected error analyzing repository {repo_name_str}: {str(e)}")
            if self.verbose: traceback.print_exc()
            return [] # Return empty list on other errors to allow process to continue
    
    async def _get_fork_contributors(self, repo_name: str, limit: int = 0, tier: int = 99) -> Dict[str, int]:
        contributors: Dict[str, int] = {}
        page_num = 1
        total_forks_processed = 0
        quality_forks_found = 0
        print(f"  [ForkAnalysis] Starting for {repo_name}, limit={limit}, tier={tier}", flush=True)
        
        # Statistics for debugging
        filtered_by_stars = 0
        filtered_by_age = 0
        
        # Quality thresholds based on tier
        min_stars = 1 if tier <= 2 else 0  # Require at least 1 star for high-tier repos
        max_days_since_update = 365 if tier <= 2 else 730  # 1 year for high-tier, 2 years for others
        
        # Additional quality thresholds for popular repositories
        # Foundry, for example, has thousands of forks - we need stricter filtering
        is_popular_repo = any(name in repo_name.lower() for name in ['foundry', 'reth', 'revm', 'alloy'])
        if is_popular_repo:
            min_stars = max(2, min_stars)  # At least 2 stars for popular repos
            max_days_since_update = min(180, max_days_since_update)  # 6 months max for popular repos

        while True:
            if limit > 0 and quality_forks_found >= limit:
                print(f"  [ForkAnalysis] Reached quality fork limit of {limit} for {repo_name}", flush=True)
                break
            
            if self.verbose: 
                print(f"  [ForkAnalysis] Fetching forks for {repo_name} (page {page_num})", flush=True)
            
            try:
                # Fetch forks sorted by recently updated
                code, fork_page_data = await self.github.get_async(
                    f"repos/{repo_name}/forks", 
                    params={"page": page_num, "sort": "updated", "direction": "desc"} 
                )
                print(f"  [ForkAnalysis] Page {page_num} for {repo_name}: Status {code}, Items: {len(fork_page_data) if isinstance(fork_page_data, list) else 'N/A'}", flush=True)

                if code != 200:
                    print(f"  [ForkAnalysis] Error {code} fetching forks for {repo_name}: {fork_page_data.get('message', 'N/A') if isinstance(fork_page_data, dict) else 'Unknown error data'}", flush=True)
                    break
                
                if not fork_page_data or not isinstance(fork_page_data, list):
                    if self.verbose: print(f"  [ForkAnalysis] No more forks found for {repo_name} on page {page_num}. Loop terminating.", flush=True)
                    break
                
                forks_on_page = len(fork_page_data)
                print(f"  [ForkAnalysis] Processing {forks_on_page} forks from page {page_num} for {repo_name}", flush=True)
                
                # Track if we're seeing too many old forks (optimization)
                old_forks_in_page = 0
                
                for i, fork_data in enumerate(fork_page_data):
                    if self.verbose and (i % 10 == 0 or i == forks_on_page -1) : # Log every 10th fork and the last one
                         print(f"    [ForkAnalysis] Processing fork {i+1}/{forks_on_page} on page {page_num} for {repo_name}...", flush=True)
                    if not isinstance(fork_data, dict): continue
                    
                    owner = fork_data.get("owner", {}).get("login")
                    if not owner:
                        continue
                        
                    # Quality filters
                    stars = fork_data.get("stargazers_count", 0)
                    if stars < min_stars:
                        filtered_by_stars += 1
                        continue  # Skip forks with insufficient stars
                    
                    # Check last update time
                    updated_at = fork_data.get("updated_at")
                    if updated_at:
                        try:
                            from datetime import datetime, timezone
                            update_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                            days_since_update = (datetime.now(timezone.utc) - update_time).days
                            if days_since_update > max_days_since_update:
                                old_forks_in_page += 1
                                if old_forks_in_page > forks_on_page * 0.8:  # If 80% are old, likely all remaining are old too
                                    print(f"  [ForkAnalysis] Too many old forks on page {page_num}, stopping early", flush=True)
                                    if self.verbose or is_popular_repo:
                                        print(f"  [ForkAnalysis] Filtered out: {filtered_by_stars} by stars, {filtered_by_age} by age", flush=True)
                                    return dict(sorted(contributors.items(), key=lambda x: x[1], reverse=True))
                                filtered_by_age += 1
                                continue  # Skip old forks
                        except Exception as e:
                            if self.verbose: print(f"    [ForkAnalysis] Error parsing date for fork: {e}", flush=True)
                    
                    # If we get here, it's a quality fork
                    
                    # Calculate contributor score based on various factors
                    score = 1  # Base score
                    score += min(stars * 2, 20)  # Up to 20 points for stars (capped at 10 stars)
                    
                    # Enhanced scoring for high-quality forks
                    if stars >= 5:
                        score += 5  # Significant bonus for well-starred forks
                    if stars >= 10:
                        score += 10  # Major bonus for highly-starred forks
                    
                    # Bonus for forks of high-tier repos
                    if tier <= 1:
                        score += 5
                    elif tier <= 3:
                        score += 2
                    
                    # Check if it's a notable fork (has description different from parent)
                    if fork_data.get("description") and fork_data.get("description") != "":
                        score += 3
                        # Extra bonus if description mentions specific improvements/features
                        desc_lower = fork_data.get("description", "").lower()
                        if any(keyword in desc_lower for keyword in ['fix', 'improve', 'add', 'feature', 'enhancement', 'fork']):
                            score += 5  # Indicates active development
                    
                    contributors[owner] = contributors.get(owner, 0) + score
                    quality_forks_found += 1
                    
                    total_forks_processed += 1
                    if limit > 0 and quality_forks_found >= limit: 
                        print(f"  [ForkAnalysis] Processed {total_forks_processed} total, {quality_forks_found} quality forks, limit {limit} reached.", flush=True)
                        break # Break from inner loop
                
                if limit > 0 and quality_forks_found >= limit: # Check again to break outer loop
                    break

                if forks_on_page < self.github.per_page: 
                    if self.verbose: print(f"  [ForkAnalysis] Reached end of forks for {repo_name} (page {page_num} had {forks_on_page} < {self.github.per_page} items per page). Loop terminating.", flush=True)
                    break
                page_num += 1
            except GitHubRateLimitError as rle:
                print(f"  [ForkAnalysis] GitHubRateLimitError on page {page_num} for {repo_name}: {rle}", flush=True)
                raise
            except GitHubAuthError as gae:
                print(f"  [ForkAnalysis] GitHubAuthError on page {page_num} for {repo_name}: {gae}", flush=True)
                raise
            except Exception as e_fork_page:
                print(f"  [ForkAnalysis] Error processing forks page {page_num} for {repo_name}: {type(e_fork_page).__name__} - {str(e_fork_page)}", flush=True)
                if self.verbose: traceback.print_exc()
                break
        
        print(f"  [ForkAnalysis] Finished for {repo_name}. Total forks processed: {total_forks_processed}. Quality forks found: {quality_forks_found}. Contributors identified: {len(contributors)}", flush=True)
        if self.verbose or is_popular_repo:
            print(f"  [ForkAnalysis] Filtered out: {filtered_by_stars} by stars, {filtered_by_age} by age", flush=True)
        
        return dict(sorted(contributors.items(), key=lambda x: x[1], reverse=True))
        
    async def analyze_user(self, username: str, repo_source: str) -> Optional[GitHubProfile]:
        repo_source_str = str(repo_source)
        if username in self.profiles:
            profile = self.profiles[username]
            if repo_source_str != "unknown":
                if repo_source_str not in profile.repos_appeared_in:
                    profile.repos_appeared_in.append(repo_source_str)
                    # First try to get tier from repo_tiers (covers both fork and PR analysis)
                    repo_tier = self.repo_tiers.get(repo_source_str, 99)
                    # If not found, check pr_merger_details as fallback
                    if repo_tier == 99:
                        for r, _, t in self.pr_merger_details.get(username, []):
                            if r == repo_source_str: repo_tier = t; break
                    
                    # Check if this cross_repo_detail already exists to avoid duplicates
                    exists = any(crd.repo == repo_source_str for crd in profile.cross_repo_details)
                    if not exists:
                        profile.cross_repo_details.append(CrossRepoDetail(repo=repo_source_str, tier=repo_tier))
            self.analyzed_users.add(username)
            return profile
            
        try:
            # Analyze user using profile analyzer to populate data
            profile = await self.profile_analyzer.analyze_user(username)
            
            if not profile:
                if self.verbose: print(f"  ❌ Received None profile for {username}, skipping.")
                self.analyzed_users.add(username) # Still mark as analyzed to avoid retries
                return None
            
            # Check if this is a minimal profile (failed to fetch data)
            # A minimal profile typically has no created_at, followers=0, public_repos=0
            if (profile.created_at is None and 
                profile.followers == 0 and 
                profile.public_repos == 0 and
                profile.bio is None and
                profile.name is None):
                if self.verbose: 
                    print(f"  ⚠️ Profile for {username} appears minimal (fetch likely failed), not storing.")
                self.analyzed_users.add(username) # Still mark as analyzed to avoid retries
                return None
            
            # Update PR merger stats if applicable
            pr_count = self.pr_merger_stats.get(username, 0)
            if pr_count > 0:
                profile.is_merger = True
                profile.prs_merged = pr_count
                if username in self.pr_merger_details:
                    for repo, count, tier in self.pr_merger_details[username]:
                        if not repo or not isinstance(repo, str) or not isinstance(count, int) or count <= 0: continue
                        tier = int(tier) if isinstance(tier, (int, float)) else 99
                        # Check if this MergedPRDetail already exists
                        exists = any(mpd.repo == repo for mpd in profile.prs_merged_details)
                        if not exists:
                            profile.prs_merged_details.append(MergedPRDetail(repo=repo, pr_count=count, pr_ids=[], tier=tier))
            
            if repo_source_str != "unknown":
                if repo_source_str not in profile.repos_appeared_in: 
                    profile.repos_appeared_in.append(repo_source_str)
                
                # First try to get tier from repo_tiers (covers both fork and PR analysis)
                repo_tier_src = self.repo_tiers.get(repo_source_str, 99)
                # If not found, check pr_merger_details as fallback
                if repo_tier_src == 99:
                    for r_detail, _, t_detail in self.pr_merger_details.get(username, []):
                        if r_detail == repo_source_str: repo_tier_src = t_detail; break
                
                existing_crd = next((crd for crd in profile.cross_repo_details if crd.repo == repo_source_str), None)
                if existing_crd:
                    if repo_tier_src < existing_crd.tier: existing_crd.tier = repo_tier_src # Update if better tier
                else:
                    profile.cross_repo_details.append(CrossRepoDetail(repo=repo_source_str, tier=repo_tier_src))
            
            self.evaluator.evaluate_profile(profile) # Evaluation should also handle potentially minimal profiles gracefully
            self.profiles[username] = profile
            self.analyzed_users.add(username)
            
            # Rate limit check for checkpointing is implicitly that if an error is raised, process stops.
            # Proactive check based on threshold is harder with PyGithub abstracting direct remaining counts.
            # Could periodically call self.github.get_rate_limit_info() if needed.
            await self._check_rate_limit_and_checkpoint() 
            
            return profile
        except GitHubRateLimitError as e_limit: # Propagated by client or analyzer
            print(f"❌ Rate limit reached processing user {username}")
            # Check if rate_limit_info is on the exception (new client attempts to add it)
            if not getattr(e_limit, 'rate_limit_info', None):
                try: e_limit.rate_limit_info = await self.github._get_rate_limit_info()
                except: pass # Ignore if fetching info fails
            raise e_limit
        except GitHubAuthError as e_auth:
            print(f"🔒 Auth error processing user {username}")
            raise e_auth
        except Exception as e_user: # Catch other unexpected errors during this user's analysis
            print(f"❌ Error in GitHubProfileFinder.analyze_user for {username}: {type(e_user).__name__} - {str(e_user)}")
            if self.verbose: traceback.print_exc()
            # Decide if we should add this user to self.analyzed_users to prevent retries
            # For now, let's add them to avoid potential error loops on the same user.
            self.analyzed_users.add(username)
            return None # Return None for this user as analysis failed critically here
    
    async def analyze_repositories(
        self, repositories: List[Union[str, Tuple[str, int, str]]], 
        max_repos: int = 0, 
        checkpoint_file: Optional[str] = None, # Checkpoint file name from CLI, not full path yet
        force_reanalyze: bool = False, 
        interrupt_check: Optional[Callable[[], Awaitable[bool]]] = None
    ) -> Dict[str, GitHubProfile]:
        all_usernames_found_this_run = set()
        repo_process_count = 0
        error_count_repo_analysis = 0
        
        print(f"🔍 Starting analysis of {len(repositories)} repositories (max_repos={max_repos}, force_reanalyze={force_reanalyze})")
        print(f"📊 Current state: {len(self.analyzed_repositories)} previously analyzed, {len(self.profiles)} profiles loaded")

        # Print initial token status - show all tokens at start
        if self.token_manager:
            print("")  # Empty line for readability
            await self.token_manager.print_compact_status(self.github)
            
            # Check if all tokens are exhausted before proceeding
            is_exhausted, earliest_reset = self.token_manager.get_global_exhaustion_status()
            if is_exhausted:
                print("\n" + "="*60)
                print("❌ ALL TOKENS ARE EXHAUSTED - CANNOT PROCEED")
                print("="*60)
                
                if earliest_reset:
                    from datetime import datetime
                    import time
                    # Use local timezone for display
                    reset_dt = datetime.fromtimestamp(earliest_reset)
                    reset_str = reset_dt.strftime('%Y-%m-%d %H:%M:%S')
                    time_until_reset = earliest_reset - time.time()
                    
                    if time_until_reset < 3600:
                        time_until_str = f"{int(time_until_reset / 60)} minutes"
                    else:
                        time_until_str = f"{int(time_until_reset / 3600)} hours {int((time_until_reset % 3600) / 60)} minutes"
                    
                    print(f"\n⏰ Tokens will reset at: {reset_str}")
                    print(f"⏳ Time to wait: {time_until_str}")
                    
                print(f"\n💡 Resume when tokens reset with:")
                print(f"   ./run.py --resume latest --config YOUR_CONFIG")
                
                # Return existing profiles without doing any work
                return self.profiles
                
            print("")  # Empty line for readability
        else:
            await self.print_token_status(force=True)
            
            # For single token, check if it's exhausted
            if self.token_manager and self.token_manager.get_token_count() == 1:
                rate_limit_data = await self.github._get_rate_limit_info()
                if 'error' not in rate_limit_data:
                    core_limits = rate_limit_data.get('resources', {}).get('core', {})
                    remaining = core_limits.get('remaining', 0)
                    
                    if remaining == 0:
                        reset_timestamp = core_limits.get('reset', 0)
                        print("\n" + "="*60)
                        print("❌ TOKEN IS EXHAUSTED - CANNOT PROCEED")
                        print("="*60)
                        
                        if reset_timestamp > time.time():
                            from datetime import datetime
                            reset_dt = datetime.fromtimestamp(reset_timestamp)
                            reset_str = reset_dt.strftime('%Y-%m-%d %H:%M:%S')
                            time_until_reset = reset_timestamp - time.time()
                            
                            if time_until_reset < 3600:
                                time_until_str = f"{int(time_until_reset / 60)} minutes"
                            else:
                                time_until_str = f"{int(time_until_reset / 3600)} hours {int((time_until_reset % 3600) / 60)} minutes"
                            
                            print(f"\n⏰ Token will reset at: {reset_str}")
                            print(f"⏳ Time to wait: {time_until_str}")
                            
                        print(f"\n💡 Resume when token resets with:")
                        print(f"   ./run.py --resume latest --config YOUR_CONFIG")
                        
                        # Return existing profiles without doing any work
                        return self.profiles

        # Only create initial checkpoint if we have tokens available
        if self.verbose and self.run_context:
            if not self.token_manager or not self.token_manager.get_global_exhaustion_status()[0]:
                initial_checkpoint_path = self._create_checkpoint(force=True)
                if initial_checkpoint_path: print(f"📝 Initial checkpoint: {Path(initial_checkpoint_path).name}")

        repos_to_process_q = list(repositories) # Make a copy

        if not force_reanalyze and self.analyzed_repositories:
            original_len = len(repos_to_process_q)
            
            # Debug: Print what's in analyzed_repositories
            if self.verbose:
                print(f"📋 Previously analyzed repositories: {list(self.analyzed_repositories)[:5]}...")  # Show first 5
            
            # Extract repo names for comparison
            repo_names_to_check = []
            for repo_item in repos_to_process_q:
                repo_name = self._validate_repo_name(repo_item[0] if isinstance(repo_item, tuple) else repo_item)
                if repo_name:
                    repo_names_to_check.append(repo_name)
                    if self.verbose and repo_name in self.analyzed_repositories:
                        print(f"  ✓ Will skip: {repo_name} (already analyzed)")
            
            repos_to_process_q = [
                repo_item for repo_item in repos_to_process_q
                if self._validate_repo_name(repo_item[0] if isinstance(repo_item, tuple) else repo_item) not in self.analyzed_repositories
            ]
            skipped = original_len - len(repos_to_process_q)
            if skipped > 0: 
                print(f"📊 Skipping {skipped} previously analyzed repositories.")
                if self.verbose and len(repos_to_process_q) > 0:
                    next_repo = self._validate_repo_name(repos_to_process_q[0][0] if isinstance(repos_to_process_q[0], tuple) else repos_to_process_q[0])
                    print(f"📋 Next repo to process: {next_repo}")

        try:
            while repos_to_process_q and (max_repos == 0 or repo_process_count < max_repos):
                if interrupt_check and await interrupt_check():
                    print("\n🛑 Interrupt detected, stopping analysis...")
                    break
                
                repo_entry = repos_to_process_q.pop(0)
                repo_name_validated, tier, label = self._parse_repo_entry(repo_entry)

                if not repo_name_validated:
                    if self.verbose: print(f"⚠️ Invalid or unparsable repository entry: {repo_entry}")
                    continue
                
                # Secondary check, in case list wasn't pre-filtered (e.g. force_reanalyze was true initially)
                if not force_reanalyze and repo_name_validated in self.analyzed_repositories:
                    if self.verbose: print(f"  ↪ Already analyzed {repo_name_validated}, skipping.")
                    continue

                label = repo_entry[2] if len(repo_entry) > 2 else ""
                label_str = f" - {label}" if label else ""
                print(f"\n🔍 Analyzing repository: {repo_name_validated} (Tier {tier}){label_str}")
                
                # Print token status before starting repository analysis
                if not self.verbose:  # In verbose mode it's already printed after each repo
                    await self.print_token_status(force=True)

                tier_label_str = f" (Tier {tier})" if tier != 99 else ""
                if label: tier_label_str += f" - {label}"
                print(f"🔍 Analyzing repository: {repo_name_validated}{tier_label_str}")
                repo_process_count += 1
                
                try:
                    usernames_from_repo = await self.analyze_repository(repo_name_validated, limit=0, tier=tier)
                    if usernames_from_repo:
                        all_usernames_found_this_run.update(usernames_from_repo)
                    else:
                        usernames_from_repo = [] # ensure it is a list

                    print(f"  👤 Analyzing {len(usernames_from_repo)} users from {repo_name_validated}")
                    if usernames_from_repo:
                        user_analysis_tasks = [self.analyze_user(uname, repo_name_validated) for uname in usernames_from_repo]
                        # Concurrency is managed by self.github.semaphore via analyze_user -> profile_analyzer -> client
                        results = await asyncio.gather(*user_analysis_tasks, return_exceptions=True)
                        
                        analyzed_count_repo = 0
                        for i, res in enumerate(results):
                            if isinstance(res, GitHubProfile): analyzed_count_repo += 1
                            elif isinstance(res, (GitHubRateLimitError, GitHubAuthError)): raise res # Critical, stop this repo
                            elif isinstance(res, Exception):
                                print(f"    ❌ Error processing user {usernames_from_repo[i]} in {repo_name_validated}: {str(res)}")
                        print(f"    📊 Finished user batch for {repo_name_validated}. Profiles updated/fetched: {analyzed_count_repo}")

                    self.analyzed_repositories.add(repo_name_validated)
                    if self.run_context: # Only checkpoint if run_context exists
                        new_chkpt = self._create_checkpoint(all_users=all_usernames_found_this_run)
                        if new_chkpt: print(f"  💾 Checkpoint: {Path(new_chkpt).name}")

                    # Success! Continue to next repository
                    repo_process_count += 1
                    
                    # Print token status after each repository
                    await self.print_token_status()
                    
                    # Checkpointing logic can be enhanced here, e.g. after every N repos:
                    if repo_process_count % 5 == 0 and self.run_context: # Checkpoint every 5 repos
                        checkpoint_path = self._create_checkpoint(all_users=all_usernames_found_this_run)
                        if checkpoint_path and self.verbose: print(f"📝 Periodic checkpoint: {Path(checkpoint_path).name}")

                except GitHubRateLimitError as e_crit:
                    # Check for global exhaustion attribute if it exists on the exception
                    is_globally_exhausted = getattr(e_crit, 'global_exhaustion', False)
                    earliest_reset_ts = getattr(e_crit, 'earliest_reset_timestamp', None)

                    if is_globally_exhausted:
                        print(f"‼️ GLOBALLY RATE LIMITED processing {repo_name_validated}.")
                        if earliest_reset_ts:
                            reset_dt = datetime.fromtimestamp(earliest_reset_ts)
                            print(f"  All tokens exhausted. Next potential reset time: {reset_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                        else:
                            print("  All tokens exhausted. Unknown reset time. Please wait a significant period (e.g., 1 hour).")
                        print("  Saving checkpoint and exiting due to global rate limit exhaustion.")
                        
                        # Create checkpoint immediately before breaking
                        if self.run_context:
                            try:
                                emergency_checkpoint = self._create_checkpoint(all_users=all_usernames_found_this_run, force=True)
                                if emergency_checkpoint:
                                    print(f"  💾 Emergency checkpoint saved: {Path(emergency_checkpoint).name}")
                                else:
                                    print("  ❌ Failed to create emergency checkpoint!")
                            except Exception as e_checkpoint:
                                print(f"  ❌ Error creating emergency checkpoint: {str(e_checkpoint)}")
                                if self.verbose: traceback.print_exc()
                        
                        # No need to re-raise here, the finally block will handle checkpointing and closing.
                        # We break the loop to proceed to finally.
                        break # Break the while repos_to_process_q loop
                    else:
                        # Not globally exhausted, or attribute not set - treat as regular rate limit for this repo/user
                        print(f"‼️ Critical API Rate Limit error processing {repo_name_validated}, stopping its analysis: {e_crit.message}")
                        # Consider adding it back to queue if it's a rate limit and retry strategy is desired here.
                        # For now, we let it be caught by the outer finally to checkpoint and close if it propagates from analyze_user.
                        # If it was raised directly from analyze_repository, this catch stops this repo.
                        # If we want the whole process to stop on any critical rate limit, re-raise e_crit here.
                        # For now, just this repo is stopped by this specific catch, allowing outer loop to continue (unless `break` above was hit)
                        pass # Allow loop to continue to next repo if not global exhaustion
                
                except GitHubAuthError as e_crit: # Keep existing auth error handling
                    print(f"‼️ Critical API Auth error processing {repo_name_validated}, stopping its analysis: {type(e_crit).__name__}")
                    raise 
                except Exception as e_repo_gen:
                    error_count_repo_analysis += 1
                    print(f"❌ Error during main analysis of repository {repo_name_validated}: {str(e_repo_gen)}")
                    if error_count_repo_analysis >= 5: # Stop if too many generic errors
                        print("Too many repository analysis errors, stopping further repository processing.")
                        break
            
            print(f"✅ Analysis loop complete. Profiles: {len(self.profiles)}, Repos analyzed this run: {repo_process_count}")
            return self.profiles
        finally:
            # Only create final checkpoint if we actually did some work
            if self.run_context and repo_process_count > 0: 
                print("ℹ️ Ensuring final checkpoint is created...")
                final_chkpt = self._create_checkpoint(all_users=all_usernames_found_this_run, force=True)
                if final_chkpt:
                    print(f"✅ Final checkpoint: {Path(final_chkpt).name}")
                else:
                    print("⚠️ Final checkpoint creation failed or was skipped.")
            await self.close()
            if self.verbose: print("👋 Exiting gracefully...")
        
    def _validate_repo_name(self, repo: Any) -> Optional[str]:
        if isinstance(repo, str) and '/' in repo:
            parts = repo.split('/')
            if len(parts) == 2 and parts[0] and parts[1]: return repo
        elif isinstance(repo, dict):
            if 'full_name' in repo: return str(repo['full_name'])
            # Add other dict parsing if needed
        # Add other type handling if necessary
        return None

    def _parse_repo_entry(self, repo_entry: Union[str, Tuple[str, int, str]]) -> Tuple[Optional[str], int, str]:
        repo_name, tier, label = None, 99, ""
        if isinstance(repo_entry, tuple):
            if len(repo_entry) >= 1: repo_name = self._validate_repo_name(repo_entry[0])
            if len(repo_entry) >= 2 and isinstance(repo_entry[1], int): tier = repo_entry[1]
            if len(repo_entry) >= 3 and isinstance(repo_entry[2], str): label = repo_entry[2]
        else:
            repo_name = self._validate_repo_name(repo_entry)
        return repo_name, tier, label

    def _calculate_progressive_limit(self, base_limit: int, tier: int) -> int:
        """Calculate progressive limits based on tier to conserve API calls for lower priority repos"""
        if base_limit == 0:  # No limit specified
            # Apply default limits based on tier
            tier_limits = {
                0: 0,     # No limit for Tier 0 (most important)
                1: 0,     # No limit for Tier 1
                2: 200,   # Moderate limit for Tier 2
                3: 150,   # Reduced for Tier 3
                4: 100,   # Further reduced
                5: 75,    # And so on...
                6: 50,
                7: 50,
                8: 30
            }
            return tier_limits.get(tier, 30)  # Default to 30 for unknown tiers
        else:
            # Scale down the user-provided limit based on tier
            scale_factors = {
                0: 1.0,   # Full limit for Tier 0
                1: 1.0,   # Full limit for Tier 1
                2: 0.8,   # 80% for Tier 2
                3: 0.6,   # 60% for Tier 3
                4: 0.5,   # 50% for Tier 4
                5: 0.4,   # And so on...
                6: 0.3,
                7: 0.3,
                8: 0.2
            }
            factor = scale_factors.get(tier, 0.2)
            return max(10, int(base_limit * factor))  # Minimum of 10

    async def _check_fork_ahead_commits(self, owner: str, repo: str, parent_owner: str, parent_repo: str) -> int:
        """Check how many commits a fork is ahead of its parent. Returns -1 on error."""
        try:
            # Compare fork with parent to see commits ahead
            code, compare_data = await self.github.get_async(
                f"repos/{owner}/{repo}/compare/{parent_owner}:{parent_repo}:main...{owner}:{repo}:main"
            )
            if code == 200 and isinstance(compare_data, dict):
                return compare_data.get("ahead_by", 0)
            elif code == 404:
                # Try with 'master' branch instead
                code, compare_data = await self.github.get_async(
                    f"repos/{owner}/{repo}/compare/{parent_owner}:{parent_repo}:master...{owner}:{repo}:master"
                )
                if code == 200 and isinstance(compare_data, dict):
                    return compare_data.get("ahead_by", 0)
        except Exception as e:
            if self.verbose:
                print(f"    [ForkAnalysis] Error checking ahead commits for {owner}/{repo}: {e}")
        return -1  # Error or no data

    async def _get_pr_mergers(self, repo_name: str, limit: int = 0, tier: int = 99) -> Dict[str, int]:
        mergers_in_repo: Dict[str, int] = {}
        page_num = 1
        total_prs_processed = 0

        print(f"  🏆 Repository {repo_name} has tier: {tier}")
        print(f"  📥 Starting to fetch PRs (limit: {limit if limit > 0 else 'unlimited'})...")
        while True:
            if limit > 0 and total_prs_processed >= limit: # limit on PRs processed
                print(f"  ✅ Reached PR processing limit of {limit} for {repo_name}")
                break

            if self.verbose: print(f"  ⏳ Fetching merged PRs from {repo_name} (page {page_num})")
            try:
                code, pr_page_data = await self.github.get_async(
                    f"repos/{repo_name}/pulls", 
                    params={"state": "closed", "page": page_num, "sort": "updated", "direction": "desc"}
                )
                if code != 200:
                    print(f"  ❌ Error {code} fetching PRs for {repo_name}: {pr_page_data.get('message', 'N/A')}")
                    break
                if not pr_page_data or not isinstance(pr_page_data, list):
                    if self.verbose: print(f"  ✅ No more PRs found for {repo_name} on page {page_num}.")
                    break

                print(f"  📋 Processing page {page_num} with {len(pr_page_data)} PRs...")
                merged_count_on_page = 0
                for pr_data in pr_page_data:
                    total_prs_processed += 1
                    if not isinstance(pr_data, dict): continue
                    
                    # Check if PR was merged (not just closed)
                    merged_at = pr_data.get("merged_at")
                    if not merged_at: 
                        continue  # Skip non-merged PRs
                    
                    merged_count_on_page += 1
                    
                    # Get the merger info
                    merged_by_data = pr_data.get("merged_by")
                    if isinstance(merged_by_data, dict):
                        merger_login = merged_by_data.get("login")
                        if merger_login and isinstance(merger_login, str):
                            mergers_in_repo[merger_login] = mergers_in_repo.get(merger_login, 0) + 1
                            # Update global stats immediately too
                            self.pr_merger_stats[merger_login] = self.pr_merger_stats.get(merger_login, 0) + 1
                    else:
                        # Sometimes merged_by can be null even if merged_at exists
                        # This happens when the merger account is deleted
                        if self.verbose:
                            pr_number = pr_data.get("number", "?")
                            print(f"    ⚠️ PR #{pr_number} was merged but merger info is missing")
                    
                    if limit > 0 and total_prs_processed >= limit: break
                
                print(f"    → Found {merged_count_on_page} merged PRs on page {page_num}")
                
                # Early termination logic: if we've processed enough pages with few merged PRs, stop
                if page_num >= 3 and len(mergers_in_repo) < 5:
                    print(f"  ⚠️ Only found {len(mergers_in_repo)} mergers after {page_num} pages, stopping early")
                    break
                
                if len(pr_page_data) < self.github.per_page: 
                    if self.verbose: print(f"  ✅ Reached end of PRs for {repo_name}.")
                    break
                page_num += 1
            except GitHubRateLimitError: raise
            except GitHubAuthError: raise
            except Exception as e_pr_page:
                print(f"  ❌ Error processing PRs page {page_num} for {repo_name}: {str(e_pr_page)}")
                break
        
        # Update pr_merger_details for all mergers found in this repo call
        for merger, count in mergers_in_repo.items():
            detail_tuple = (repo_name, count, tier)
            # Avoid duplicates in self.pr_merger_details[merger]
            if not any(d[0] == repo_name for d in self.pr_merger_details.get(merger, [])):
                self.pr_merger_details[merger].append(detail_tuple)
            else: # Update if already exists (e.g. if tier logic changes or re-analyzing)
                for i, existing_detail in enumerate(self.pr_merger_details.get(merger, [])):
                    if existing_detail[0] == repo_name:
                        self.pr_merger_details[merger][i] = detail_tuple
                        break

        print(f"  ✅ Found {len(mergers_in_repo)} PR mergers in {repo_name} (processed {total_prs_processed} PRs)")
        return dict(sorted(mergers_in_repo.items(), key=lambda x: x[1], reverse=True))
    
    async def _check_rate_limit_and_checkpoint(self): # Review this for PyGithub
        """Check rate limit and create checkpoint if approaching the limit or if needed.
        With PyGithub, direct remaining counts per token are less visible. 
        Rotation happens on RateLimitExceededException. Checkpointing might be more time-based or after N users.
        """
        try:
            # This is a simplified check. A robust solution would involve TokenManager 
            # having a way to report overall health or if a rotation just occurred due to exhaustion.
            # For now, we rely on exceptions to stop the process if all tokens are truly out.
            # We can, however, proactively fetch the current token's rate limit for logging/decision.
            rate_limit_data = await self.github._get_rate_limit_info() # Use the client's internal method
            core_limits = rate_limit_data.get("resources", {}).get("core", {})
            remaining = core_limits.get("remaining", 9999)
            limit = core_limits.get("limit", 9999)
            
            if self.verbose:
                print(f"  💡 Rate limit check: {remaining}/{limit} remaining for current token.")

            # If remaining is very low (e.g., below a threshold like self.rate_limit_threshold,
            # which is currently 200 by default), it's a good time to checkpoint.
            # However, PyGithub's built-in retry and our client's rotation might handle it.
            # Forcing a checkpoint here might be too frequent if rotation is effective.
            # Let's primarily rely on periodic checkpointing after repo analysis or if an error occurs.
            
            # Placeholder: For now, this method won't force a checkpoint based on low 'remaining'
            # as the new client handles rotation more internally. Checkpoints occur after repo analysis.
            pass

        except GitHubRateLimitError: # If even checking rate limit fails due to limits
            print("⚠️ Rate limit seems exhausted even when checking. Strongly consider stopping or waiting.")
            # This might be a good place to force a checkpoint if self.run_context is available.
            # if self.run_context: self._create_checkpoint(force=True)
            raise # Re-raise to stop current operation
        except Exception as e_rl_check:
            if self.verbose: print(f"  ⚠️ Could not check rate_limit proactively: {str(e_rl_check)}")

    def _create_checkpoint(self, all_users: Optional[Set[str]] = None, remaining_users: Optional[Set[str]] = None, force: bool = False) -> Optional[str]:
        """Create a checkpoint with current state. Enhanced with better error handling."""
        if not self.checkpoint_manager:
            return None

        # Standardize data for checkpoint (mostly lists of strings or simple dicts)
        try:
            if self.verbose: print(f"📝 Creating checkpoint... Repos: {len(self.analyzed_repositories)}, Users: {len(self.analyzed_users)}, Profiles: {len(self.profiles)}")
            
            # Analyzed repositories are already strings
            analyzed_repos_list = list(self.analyzed_repositories)
            
            pr_merger_details_serializable = { 
                user: [list(detail) for detail in details_list] 
                for user, details_list in self.pr_merger_details.items()
            }
            contributor_stats_serializable = { 
                user: dict(stats) 
                for user, stats in self.contributor_stats.items() 
            }

            checkpoint_file_path = self.checkpoint_manager.save_checkpoint(
                analyzed_users=list(self.analyzed_users),
                analyzed_repositories=analyzed_repos_list,
                profiles=self.profiles, # Profile.to_dict() will be called by CheckpointManager
                pr_merger_stats=dict(self.pr_merger_stats),
                pr_merger_details=pr_merger_details_serializable,
                contributor_stats=contributor_stats_serializable,
                all_users=list(all_users or set()),
                # remaining_users: Not explicitly tracked this way anymore, can be derived or omitted
                repo_tiers=self.repo_tiers  # Save repo tiers mapping
            )
            if self.verbose and checkpoint_file_path:
                print(f"✅ Checkpoint data prepared for saving to {Path(checkpoint_file_path).name}")
            return checkpoint_file_path
        except Exception as e_chkpt:
            print(f"❌ Error creating checkpoint data: {str(e_chkpt)}")
            if self.verbose: traceback.print_exc()
            return None
            
    async def get_rate_limit_info(self) -> Dict:
        """Get current rate limit information"""
        try:
            return await self.github._get_rate_limit_info()
        except Exception as e:
            return {"error": str(e)}
            
    async def print_token_status(self, force: bool = False) -> None:
        """Print current token status if verbose or forced"""
        if not (self.verbose or force):
            return
            
        # If we have multiple tokens, show compact status for all
        if self.token_manager and self.token_manager.get_token_count() > 1:
            await self.token_manager.print_compact_status(self.github)
            return
            
        # Single token - show detailed status
        try:
            # Get current token info
            rate_limit_data = await self.github._get_rate_limit_info()
            if 'error' not in rate_limit_data:
                core_limits = rate_limit_data.get('resources', {}).get('core', {})
                remaining = core_limits.get('remaining', 0)
                limit = core_limits.get('limit', 5000)
                reset_timestamp = core_limits.get('reset', 0)
                
                # Get current token identifier
                current_token = self.github.current_token
                token_display = f"{current_token[:8]}..." if current_token else "Unknown"
                
                # Calculate percentage
                percentage = (remaining / limit * 100) if limit > 0 else 0
                
                # Format reset time if needed
                if remaining < 1000 and reset_timestamp > time.time():
                    from datetime import datetime
                    reset_dt = datetime.fromtimestamp(reset_timestamp)
                    reset_str = f" (resets at {reset_dt.strftime('%H:%M:%S')})"
                else:
                    reset_str = ""
                
                # Print status
                status_emoji = "🟢" if percentage > 50 else "🟡" if percentage > 20 else "🔴"
                print(f"{status_emoji} Token {token_display}: {remaining}/{limit} API calls remaining ({percentage:.1f}%){reset_str}")
                    
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Could not check token status: {str(e)}")
            
    async def close(self) -> None:
        """Close the GitHub client session (no-op for PyGithub based client)"""
        await self.github.close_session() # Client now has this method
    
    def print_profile_summary(self) -> None:
        if not self.profiles: print("❌ No profiles to summarize"); return
        # ... (summary printing logic - should be largely unaffected if Profile/Evaluation objects are consistent)
        # This method is synchronous and uses data already in memory.
        # Ensure GitHubProfile and ProfileEvaluation are correctly populated.
        categories = defaultdict(list)
        for username, profile in self.profiles.items():
            if profile.evaluation:
                categories[profile.evaluation.category].append(profile)
        # ... rest of the method from original ...
        print("\n📊 Profile Summary")
        print(f"Total profiles: {len(self.profiles)}")
        # Correct sorting for categories
        sorted_categories = sorted(categories.items(), key=lambda x: (
            0 if "Outstanding" in x[0] else 
            1 if "Excellent" in x[0] else 
            2 if "Very Good" in x[0] else 
            3 if "Good" in x[0] else 
            4 if "Average" in x[0] else 5
        ))

        for category_name, cat_profiles in sorted_categories:
            highlight = "🔍" if "Hiring Interest" in category_name else "✨"
            print(f"\n{highlight} {category_name} ({len(cat_profiles)} profiles)")
            # Sort profiles within category by score
            cat_profiles.sort(key=lambda p: p.evaluation.total_score if p.evaluation else 0, reverse=True)
            for prof in cat_profiles[:10]: # Top 10
                score = prof.evaluation.total_score if prof.evaluation else 0
                name_display = prof.name or prof.username
                pr_info_str = f" ({prof.prs_merged} PRs merged)" if prof.is_merger and prof.prs_merged > 0 else ""
                openness_str = ""
                if prof.evaluation and prof.evaluation.has_openness_signals and prof.evaluation.explicit_interest_details:
                    openness_str = f" - 💼 {prof.evaluation.explicit_interest_details[0]}"
                    if len(prof.evaluation.explicit_interest_details) > 1:
                        openness_str += f" (+{len(prof.evaluation.explicit_interest_details)-1} more)"
                print(f"  - {name_display} (Score: {score:.1f}){pr_info_str}{openness_str} - {prof.profile_url}")

        if self.run_context:
            self.generate_ai_prompt()
            
    def generate_ai_prompt(self) -> None:
        if not self.profiles: print("❌ No profiles for AI prompt"); return
        if not self.run_context: print("❌ No run_context for AI prompt path"); return
        
        if self.verbose: print(f"\n🔍 Generating AI prompt to: {self.run_context.ai_prompt_file}")
        # ... (AI prompt generation logic - ensure Profile/Evaluation attributes are correct)
        # This method is synchronous and uses data already in memory.
        profile_dicts_for_prompt = []
        for username, profile_obj in self.profiles.items():
            if profile_obj.evaluation: # Only include profiles that have been evaluated
                # Assuming profile_obj.to_dict() provides the necessary structure
                # or manually construct the dict as in the original if to_dict() is not sufficient/present.
                # For now, let's assume Profile.to_dict() is updated or we use specific attrs.
                eval_dict = profile_obj.evaluation.__dict__ # Quick way if dataclass, or make a to_dict()
                prof_dict = {
                    "username": profile_obj.username,
                    "name": profile_obj.name, 
                    "location": profile_obj.location,
                    "company": profile_obj.company,
                    "email": profile_obj.email,
                    "blog": profile_obj.blog,
                    "twitter_username": profile_obj.twitter_username,
                    "followers": profile_obj.followers,
                    "public_repos": profile_obj.public_repos,
                    "languages": profile_obj.languages[:5], # Top 5 languages
                    "bio": profile_obj.bio,
                    "is_merger": profile_obj.is_merger,
                    "prs_merged": profile_obj.prs_merged,
                    "explicit_interest_signal": profile_obj.explicit_interest_signal,
                    "recent_activity_spike_signal": profile_obj.recent_activity_spike_signal,
                    "evaluation": {
                        "category": eval_dict.get("category"),
                        "total_score": eval_dict.get("total_score"),
                        "has_openness_signals": eval_dict.get("has_openness_signals"),
                        "explicit_interest_details": eval_dict.get("explicit_interest_details"),
                        "highest_pr_tier": eval_dict.get("highest_pr_tier")
                    },
                    "top_repos": [tr.__dict__ for tr in profile_obj.top_repos[:3]] if profile_obj.top_repos else [] # Top 3 repos
                }
                profile_dicts_for_prompt.append(prof_dict)

        if not profile_dicts_for_prompt:
            print("ℹ️ No evaluated profiles to generate AI prompt.")
            return

        generate_prompt(profile_dicts_for_prompt, str(self.run_context.ai_prompt_file))
        # Verification logic for file creation can remain.
        if Path(self.run_context.ai_prompt_file).exists():
            print(f"✅ Verified AI prompt file: {self.run_context.ai_prompt_file} ({Path(self.run_context.ai_prompt_file).stat().st_size} bytes)")
        else:
            print(f"❌ AI prompt file NOT created: {self.run_context.ai_prompt_file}")
            # Fallback directory creation and write attempt (from original)
            try:
                Path(self.run_context.ai_prompt_file).parent.mkdir(parents=True, exist_ok=True)
                with open(self.run_context.ai_prompt_file, 'w', encoding='utf-8') as f:
                    # Generate prompt content - function returns string regardless of output_file parameter
                    prompt_content_str = generate_prompt(profile_dicts_for_prompt, output_file=None)
                    if prompt_content_str:
                        f.write(prompt_content_str)
                        print(f"✅ Successfully created AI prompt file (fallback): {self.run_context.ai_prompt_file}")
                    else:
                         f.write("# No profiles available for analysis (fallback write).")
                         print(f"⚠️ Wrote empty AI prompt file (fallback): {self.run_context.ai_prompt_file}")
            except Exception as e_prompt_fb:
                print(f"❌ Failed to create AI prompt file (fallback): {str(e_prompt_fb)}") 

    def generate_llm_analysis_output(self) -> str:
        """Generate a structured output of all profiles for LLM analysis"""
        if not self.profiles:
            return "No profiles available for analysis."
        
        output = []
        output.append("# GitHub Developer Analysis Report")
        output.append(f"\nTotal profiles analyzed: {len(self.profiles)}")
        output.append("\n" + "="*80 + "\n")
        
        # Sort profiles by evaluation score
        sorted_profiles = sorted(
            self.profiles.items(),
            key=lambda x: x[1].evaluation.total_score if x[1].evaluation else 0,
            reverse=True
        )
        
        for rank, (username, profile) in enumerate(sorted_profiles, 1):
            output.append(f"## Rank #{rank}: {profile.name or username} (@{username})")
            
            # Basic info
            output.append(f"\n**Profile URL**: {profile.profile_url}")
            if profile.location:
                output.append(f"**Location**: {profile.location}")
            if profile.company:
                output.append(f"**Company**: {profile.company}")
            if profile.email:
                output.append(f"**Email**: {profile.email}")
            if profile.bio:
                output.append(f"**Bio**: {profile.bio[:200]}{'...' if len(profile.bio) > 200 else ''}")
            
            # GitHub stats
            output.append(f"\n### GitHub Statistics")
            output.append(f"- **Followers**: {profile.followers}")
            output.append(f"- **Public Repos**: {profile.public_repos}")
            output.append(f"- **Account Age**: {profile.created_at[:10] if profile.created_at else 'Unknown'}")
            
            # Languages
            if profile.languages_detailed:
                output.append(f"\n### Programming Languages")
                for lang in profile.languages_detailed[:5]:  # Top 5
                    output.append(f"- **{lang.name}**: {lang.percentage:.1f}%")
            
            # Repository contributions
            if profile.is_merger and profile.prs_merged_details:
                output.append(f"\n### Pull Request Contributions")
                output.append(f"Total PRs merged: {profile.prs_merged}")
                for pr_detail in profile.prs_merged_details[:5]:  # Top 5
                    output.append(f"- **{pr_detail.repo}** (Tier {pr_detail.tier}): {pr_detail.pr_count} PRs")
            
            # Cross-repo activity
            if profile.cross_repo_details:
                output.append(f"\n### Cross-Repository Activity")
                output.append(f"Appeared in {len(profile.cross_repo_details)} target repositories:")
                for cr in profile.cross_repo_details[:5]:  # Top 5
                    output.append(f"- {cr.repo} (Tier {cr.tier})")
            
            # Top repositories
            if profile.top_repos:
                output.append(f"\n### Notable Personal Repositories")
                for repo in profile.top_repos[:3]:  # Top 3
                    output.append(f"- **{repo.name}**: {repo.stars}⭐ ({repo.language or 'No language'})")
                    if repo.description:
                        output.append(f"  - {repo.description[:100]}{'...' if len(repo.description) > 100 else ''}")
            
            # Evaluation details
            if profile.evaluation:
                eval_data = profile.evaluation
                output.append(f"\n### Evaluation Results")
                output.append(f"- **Category**: {eval_data.category}")
                output.append(f"- **Total Score**: {eval_data.total_score:.2f}/10")
                output.append(f"- **Rust Prominence**: {eval_data.rust_prominence}")
                output.append(f"- **Is PR Merger**: {'Yes' if eval_data.is_pr_merger else 'No'}")
                if eval_data.highest_pr_tier is not None:
                    output.append(f"- **Highest PR Tier**: {eval_data.highest_pr_tier}")
                
                # Signals
                if profile.explicit_interest_signal:
                    output.append(f"\n### 🚨 Job Search Signals")
                    if profile.bio_keywords_found:
                        output.append(f"- Bio keywords: {', '.join(profile.bio_keywords_found)}")
                    if profile.readme_keywords_found:
                        output.append(f"- README keywords: {', '.join(profile.readme_keywords_found)}")
                if profile.recent_activity_spike_signal:
                    output.append(f"- Recent activity spike detected")
                if profile.passion_project_signal:
                    output.append(f"- Active passion project detected")
            
            output.append("\n" + "-"*80 + "\n")
        
        # Add summary for LLM
        output.append("\n## Summary for Analysis")
        output.append("\nPlease analyze these developer profiles considering:")
        output.append("1. **Technical Fit**: Rust expertise, EVM/blockchain experience, systems programming")
        output.append("2. **Contribution Quality**: PR merger status, tier of repositories contributed to")
        output.append("3. **Availability Signals**: Job search indicators, recent activity patterns")
        output.append("4. **Cultural Fit**: Types of projects, contribution patterns, communication style")
        output.append("\nProvide your top 10 recommendations with reasoning for each.")
        
        return "\n".join(output)
    
    def print_llm_analysis(self, output_file: Optional[str] = None) -> None:
        """Print or save LLM analysis output"""
        analysis = self.generate_llm_analysis_output()
        
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(analysis)
                print(f"✅ LLM analysis saved to: {output_file}")
                print(f"📄 File size: {os.path.getsize(output_file):,} bytes")
            except Exception as e:
                print(f"❌ Error saving LLM analysis: {str(e)}")
                print("\nFalling back to console output...")
                print(analysis)
        else:
            print(analysis) 