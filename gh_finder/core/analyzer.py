"""
User profile and repository analysis
"""

import asyncio
import datetime
import json
import re
import base64
from typing import Dict, List, Any, Optional, Set, Tuple

from ..api.client import GitHubClient, GitHubRateLimitError, GitHubAuthError
from ..models.profile import GitHubProfile, Repository, LanguageDetail

class ProfileAnalyzer:
    """Analyzes GitHub profiles to gather detailed information"""
    
    def __init__(self, github_client: GitHubClient, verbose: bool = False):
        """Initialize profile analyzer
        
        Args:
            github_client: GitHub API client (now PyGithub based)
            verbose: Enable verbose output
        """
        self.github = github_client
        self.verbose = verbose
        
        # Openness to work signals
        self.bio_keywords = [
            "looking for", "open to", "available for", "seeking", "job hunt",
            "job search", "new opportunity", "new opportunities", "job opportunity",
            "job hunting", "unemployed", "layoff", "laid off", "hire me", "for hire",
            "seeking work", "seeking opportunities", "open for work", "available", 
            "hiring", "status: hiring"
        ]
        self.readme_keywords = [
            "looking for", "open to", "available for", "seeking", "job hunt",
            "job search", "new opportunity", "new opportunities", "job opportunity",
            "job hunting", "unemployed", "layoff", "laid off", "hire me", "for hire",
            "seeking work", "seeking opportunities", "open for work", "my resume", 
            "currently available", "job status", "employment status", "career status"
        ]
        
    async def analyze_user(self, username: str) -> Optional[GitHubProfile]:
        """Analyze a user's GitHub profile
        
        Args:
            username: GitHub username to analyze
            
        Returns:
            GitHubProfile or None if user not found or critical error.
            
        Raises:
            GitHubRateLimitError: When all tokens are rate limited (propagated from client)
            GitHubAuthError: If authentication fails (propagated from client)
        """
        if self.verbose:
            print(f"Analyzing user: {username}")
            
        profile = GitHubProfile(username=username)
        # profile.profile_readme_content is initialized in GitHubProfile now
        
        try:
            # Get PyGithub NamedUser object
            user_pygithub_obj = await self.github.get_user_pygithub_object(username)
            
            if user_pygithub_obj is None: # User not found or other critical fetch error handled by client
                print(f"User {username} not found or failed to fetch. Returning minimal profile.")
                return profile # Return the initialized, empty profile
            
            # Check if the fetched entity is an organization
            if hasattr(user_pygithub_obj, 'type') and user_pygithub_obj.type == 'Organization':
                if self.verbose:
                    print(f"Skipping analysis for {username} as it is an Organization.")
                # Optionally, you could mark the profile object as an organization if needed elsewhere,
                # but for now, just returning None effectively skips it.
                return None
                            
            # Map attributes from PyGithub NamedUser object to our GitHubProfile
            profile.name = user_pygithub_obj.name
            profile.company = user_pygithub_obj.company
            profile.blog = user_pygithub_obj.blog
            profile.location = user_pygithub_obj.location
            profile.email = user_pygithub_obj.email
            profile.hireable = user_pygithub_obj.hireable
            profile.bio = user_pygithub_obj.bio
            profile.twitter_username = user_pygithub_obj.twitter_username
            profile.public_repos = user_pygithub_obj.public_repos if user_pygithub_obj.public_repos is not None else 0
            profile.public_gists = user_pygithub_obj.public_gists if user_pygithub_obj.public_gists is not None else 0
            profile.followers = user_pygithub_obj.followers if user_pygithub_obj.followers is not None else 0
            profile.following = user_pygithub_obj.following if user_pygithub_obj.following is not None else 0
            profile.created_at = user_pygithub_obj.created_at.isoformat() if user_pygithub_obj.created_at else None
            profile.updated_at = user_pygithub_obj.updated_at.isoformat() if user_pygithub_obj.updated_at else None
            profile.profile_url = user_pygithub_obj.html_url or f"https://github.com/{username}"
            
            # Proceed with further analysis using the populated profile
            self._analyze_bio(profile) # Synchronous, uses profile.bio, profile.hireable
            await self._analyze_profile_readme(profile) # Async, fetches README content
            await self._analyze_repos_and_languages(profile) # Async, fetches repos and languages
            await self._analyze_activity_and_employer(profile) # Async, fetches events, employer is sync
            
        except GitHubRateLimitError as rle: # Re-raised by the client or other async calls here
            print(f"❌ Rate limit exceeded while analyzing user {username}: {rle.message}")
            raise
        except GitHubAuthError as gae: # Re-raised by the client or other async calls here
            print(f"🔒 Authentication error while analyzing user {username}: {gae.message}")
            raise
        except Exception as e:
            print(f"❌ Error during deeper analysis of user {username}: {type(e).__name__} - {str(e)}")
            # Basic profile data should already be set from user_pygithub_obj if it was fetched
            # Ensure profile URL is set if it somehow wasn't (should be by now)
            if not profile.profile_url:
                profile.profile_url = f"https://github.com/{username}"
            # The __init__ of GitHubProfile now initializes all necessary list/bool/Optional attributes.
            # No need for manual re-initialization here.
            # We can return the partially populated profile or None depending on desired behavior for partial failures.
            # For now, returning the profile as it is.
        
        return profile
        
    def _analyze_bio(self, profile: GitHubProfile) -> None:
        """Analyze bio for openness signals"""
        if profile.hireable:
            profile.explicit_interest_signal = True
            if self.verbose:
                print(f"  ✅ User {profile.username} has marked themselves as hireable on GitHub")

        if profile.bio:
            bio_lower = profile.bio.lower()
            # Check for explicit keywords
            for keyword in self.bio_keywords:
                if keyword in bio_lower:
                    profile.explicit_interest_signal = True
                    if keyword not in profile.bio_keywords_found:
                        profile.bio_keywords_found.append(keyword)
            
            # Check for "open to work" badge variants (simplified)
            if re.search(r"#opentowork|lookingforjob|availableforhire", bio_lower.replace(" ", "")):
                profile.open_to_work = True
                if "#opentowork" not in profile.bio_keywords_found: # Avoid duplicate generic signal
                     profile.bio_keywords_found.append("#opentowork")
            
            if profile.bio_keywords_found and self.verbose:
                print(f"  ✅ Found bio keywords for {profile.username}: {profile.bio_keywords_found}")


    async def _analyze_profile_readme(self, profile: GitHubProfile) -> None:
        """Check for profile README and analyze it for openness signals"""
        username = profile.username
        
        try:
            code, repo_data = await self.github.get_async(f"repos/{username}/{username}")
            if code != 200: 
                if self.verbose and code == 404: print(f"  ℹ️ No profile repository for {username}.")
                elif self.verbose: print(f"  ⚠️ Error {code} checking profile repository for {username}: {repo_data.get('message')}")
                return
            
            profile.profile_readme_found = True 
            default_branch = repo_data.get('default_branch', 'main') 
            
            readme_content_str = None
            readme_filenames = ["README.md", "readme.md", "Readme.md"]
            
            for readme_filename in readme_filenames:
                try:
                    readme_code, readme_file_data = await self.github.get_async(
                        f"repos/{username}/{username}/contents/{readme_filename}", 
                        params={"ref": default_branch}
                    )
                    
                    if readme_code == 200 and readme_file_data and isinstance(readme_file_data, dict) and 'content' in readme_file_data:
                        encoded_content = readme_file_data.get('content')
                        if encoded_content and isinstance(encoded_content, str):
                            decoded_bytes = base64.b64decode(encoded_content.replace('\n', ''))
                            readme_content_str = decoded_bytes.decode('utf-8', errors='ignore')
                            profile.profile_readme_content = readme_content_str # Store decoded content
                            if self.verbose: print(f"  ✅ Found and decoded profile README for {username}.")
                            break 
                        elif self.verbose: print(f"  ℹ️ README found for {username} but content was empty or not a string.")
                    elif readme_code == 404:
                        if self.verbose: print(f"  ℹ️ README file '{readme_filename}' not found for {username} in profile repo branch {default_branch}.")
                    elif self.verbose:
                         print(f"  ⚠️ Error {readme_code} fetching {readme_filename} for {username}: {readme_file_data.get('message') if isinstance(readme_file_data, dict) else 'Unknown error'}")

                except GitHubRateLimitError: raise 
                except GitHubAuthError: raise
                except Exception as e_file: 
                    if self.verbose: print(f"  ⚠️ Error processing README file {readme_filename} for {username}: {str(e_file)}")
                    continue 
            
            if profile.profile_readme_content: # Now check profile.profile_readme_content
                readme_lower = profile.profile_readme_content.lower()
                for keyword in self.readme_keywords:
                    if keyword in readme_lower:
                        profile.explicit_interest_signal = True
                        if keyword not in profile.readme_keywords_found:
                            profile.readme_keywords_found.append(keyword)
                if profile.readme_keywords_found and self.verbose:
                    print(f"  ✅ Found README keywords for {username}: {profile.readme_keywords_found}")
            elif profile.profile_readme_found and self.verbose: 
                print(f"  ℹ️ Profile repository for {username} exists, but no standard README.md found or decoded.")

        except GitHubRateLimitError: raise
        except GitHubAuthError: raise
        except Exception as e_repo:
            if self.verbose: print(f"  ❌ Error analyzing profile README for {username}: {str(e_repo)}")


    async def _get_top_repositories(self, profile: GitHubProfile) -> None:
        """Fetch user's top repositories (most recently updated)"""
        try:
            code, repo_list_data = await self.github.get_async(f"users/{profile.username}/repos", {
                "sort": "updated", 
                "direction": "desc", 
                "page": 1 
            })
            
            if code != 200:
                if self.verbose: print(f"  ⚠️ Error {code} fetching repositories for {profile.username}: {repo_list_data.get('message', 'N/A')}")
                return
                
            if not repo_list_data or not isinstance(repo_list_data, list):
                if self.verbose: print(f"  ⚠️ Invalid or empty repository data for {profile.username}")
                return
            
            for repo_data_item in repo_list_data[:10]: 
                if not isinstance(repo_data_item, dict): continue
                repo_owner_login = repo_data_item.get("owner", {}).get("login") if isinstance(repo_data_item.get("owner"), dict) else None
                
                profile.top_repos.append(Repository(
                    name=repo_data_item.get("name", ""),
                    url=repo_data_item.get("html_url", "") or f"https://github.com/{repo_owner_login or profile.username}/{repo_data_item.get('name', '')}",
                    description=repo_data_item.get("description"),
                    stars=repo_data_item.get("stargazers_count", 0),
                    language=repo_data_item.get("language"),
                    updated_at=repo_data_item.get("updated_at")
                ))
                
            if self.verbose:
                if profile.top_repos: print(f"  ✅ Found {len(profile.top_repos)} top repositories for {profile.username}")
                else: print(f"  ℹ️ No repositories found for {profile.username} (or error fetching page).")
                
            if profile.top_repos:
                # Passion project signal based on the first (most recently updated) repo from the list fetched
                # The repo_list_data is a list of dicts, so repo_data_item from the loop is one of those.
                # We need to access the _rawData from the first item of this list for the signal.
                first_repo_data = repo_list_data[0] # This is a dict from _rawData
                
                is_owner = first_repo_data.get("owner", {}).get("login") == profile.username if isinstance(first_repo_data.get("owner"), dict) else False
                is_fork = first_repo_data.get("fork", False)
                repo_name_for_signal = first_repo_data.get("name")
                repo_updated_at_for_signal = first_repo_data.get("updated_at")

                if is_owner and not is_fork and repo_name_for_signal and repo_name_for_signal != profile.username and not repo_name_for_signal.endswith("-bot"):
                    if repo_updated_at_for_signal:
                        try:
                            updated_date = datetime.datetime.fromisoformat(repo_updated_at_for_signal.replace("Z", "+00:00"))
                            now = datetime.datetime.now(datetime.timezone.utc)
                            if (now - updated_date).days <= 14: 
                                profile.passion_project_signal = True
                                if self.verbose: print(f"  ✅ Found recently updated passion project: {repo_name_for_signal}")
                        except Exception as e_date:
                            if self.verbose: print(f"  ⚠️ Error parsing date for {repo_name_for_signal}: {str(e_date)}")
        except GitHubRateLimitError: raise
        except GitHubAuthError: raise
        except Exception as e:
            if self.verbose: print(f"  ❌ Error getting top repositories for {profile.username}: {str(e)}")
        return

    async def _get_languages_for_profile(self, profile: GitHubProfile) -> None:
        """Get language statistics for the user from their top repositories"""
        lang_stats: Dict[str, int] = {}
        if not profile.top_repos:
            if self.verbose: print(f"  ℹ️ No top repositories to analyze languages for {profile.username}.")
            return

        # Limit language analysis to a smaller number of top repos to save API calls
        repos_to_analyze_langs = profile.top_repos[:5]

        for repo_model in repos_to_analyze_langs:
            if not repo_model.name: continue 
            try:
                # Determine owner from URL, as repo_model might not have structured owner info
                url_parts = repo_model.url.split('/')
                owner_login = profile.username # Default assumption
                if len(url_parts) >= 5 and url_parts[2].endswith('github.com'):
                    owner_login = url_parts[3]

                code, lang_data_dict = await self.github.get_async(f"repos/{owner_login}/{repo_model.name}/languages")
                if code == 200 and isinstance(lang_data_dict, dict):
                    for lang, bytes_count in lang_data_dict.items():
                        lang_stats[lang] = lang_stats.get(lang, 0) + bytes_count
                elif self.verbose:
                    print(f"  ⚠️ Error {code} fetching languages for {owner_login}/{repo_model.name}: {lang_data_dict.get('message') if isinstance(lang_data_dict, dict) else 'N/A'}")
            except GitHubRateLimitError: raise
            except GitHubAuthError: raise
            except Exception as e_lang:
                if self.verbose: print(f"  ❌ Error processing languages for repo {repo_model.name}: {str(e_lang)}")
                continue 

        total_bytes = sum(lang_stats.values())
        if total_bytes > 0:
            sorted_langs = sorted(lang_stats.items(), key=lambda item: item[1], reverse=True)
            profile.languages = [lang for lang, _ in sorted_langs]
            profile.languages_detailed = [
                LanguageDetail(name=lang, bytes=bytes_val, percentage=(bytes_val / total_bytes) * 100)
                for lang, bytes_val in sorted_langs
            ]
        if self.verbose and profile.languages: 
            print(f"  ✅ Analyzed languages for {profile.username}: {profile.languages[:5]}")
        elif self.verbose:
            print(f"  ℹ️ No languages detected for {profile.username}.")

    async def _analyze_recent_activity_events(self, profile: GitHubProfile) -> None:
        """Analyze recent activity for spikes (potential job search indicator)"""
        events_data_list = []
        max_events_to_fetch = 150 
        
        # Use client's per_page setting
        # Calculate max_pages based on client's per_page, ensure it's at least 1 if per_page is large.
        client_per_page = self.github.per_page if self.github.per_page > 0 else 30 # Default if 0
        max_pages_to_try = (max_events_to_fetch + client_per_page -1) // client_per_page  # Ceiling division
        max_pages_to_try = max(1, max_pages_to_try) # Ensure at least one page is tried
        if self.verbose: 
            print(f"  ⚙️ Event fetching for {profile.username}: max_events={max_events_to_fetch}, client_per_page={client_per_page}, max_pages={max_pages_to_try}")

        for page_num in range(1, max_pages_to_try + 1):
            try:
                code, page_events_data_list = await self.github.get_async(
                    f"users/{profile.username}/events", 
                    params={"page": page_num} 
                )
                if code == 200 and isinstance(page_events_data_list, list):
                    if not page_events_data_list: 
                        if self.verbose: print(f"  ℹ️ No more events for {profile.username} on page {page_num}.")
                        break
                    events_data_list.extend(page_events_data_list)
                    if self.verbose: print(f"  📄 Fetched page {page_num} with {len(page_events_data_list)} events for {profile.username}. Total: {len(events_data_list)}")
                    if len(events_data_list) >= max_events_to_fetch:
                        break 
                elif code != 200 : 
                    if self.verbose: print(f"  ⚠️ Error {code} fetching events page {page_num} for {profile.username}: {page_events_data_list.get('message') if isinstance(page_events_data_list,dict) else 'N/A'}")
                    break 
            except GitHubRateLimitError: raise
            except GitHubAuthError: raise
            except Exception as e_event_page:
                if self.verbose: print(f"  ❌ Error processing events page {page_num} for {profile.username}: {str(e_event_page)}")
                break 

        if not events_data_list:
            if self.verbose: print(f"  ℹ️ No public events found for {profile.username} after trying {max_pages_to_try} pages.")
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        week_events_count = 0
        month_events_count = 0

        for event_item_data in events_data_list:
            if not isinstance(event_item_data, dict): continue
            created_at_str = event_item_data.get("created_at")
            if created_at_str:
                try:
                    event_time = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    if (now - event_time).days <= 7:
                        week_events_count += 1
                    if (now - event_time).days <= 30:
                        month_events_count += 1
                except ValueError:
                    if self.verbose: print(f"  ⚠️ Could not parse event date: {created_at_str}")

        if month_events_count > 5: 
            weekly_average = month_events_count / 4.0 
            if week_events_count > (weekly_average * 2.0): # Adjusted threshold (e.g. 2.0x)
                profile.recent_activity_spike_signal = True
                if self.verbose: print(f"  ✅ Detected recent activity spike for {profile.username}: {week_events_count} in last week vs {weekly_average:.1f} weekly avg.")
        elif self.verbose:
            print(f"  ℹ️ Not enough monthly events ({month_events_count}) for {profile.username} to reliably detect activity spike.")
    
    def _analyze_employer_info(self, profile: GitHubProfile) -> None:
        """Analyze if the employer matches the target repository (placeholder)"""
        if not profile.company: return
        company = profile.company.strip()
        if company.startswith('@'): company = company[1:].strip()
        profile.employer_name = company

    async def _analyze_repos_and_languages(self, profile: GitHubProfile) -> None:
        """Wrapper to analyze user's repositories and then their languages"""
        await self._get_top_repositories(profile)
        await self._get_languages_for_profile(profile) 
        
    async def _analyze_activity_and_employer(self, profile: GitHubProfile) -> None:
        """Wrapper to analyze user's activity and employer info"""
        await self._analyze_recent_activity_events(profile)
        self._analyze_employer_info(profile) # Sync, no API calls 