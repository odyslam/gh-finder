"""
GitHub API client for interacting with GitHub's REST API
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import json # Kept for potential use in error data or future needs
from functools import partial

from github import Github, GithubRetry, RateLimitExceededException, BadCredentialsException, UnknownObjectException, GithubException, ContentFile
import github
from github.GithubObject import NotSet

from .token_manager import TokenManager

class GitHubAuthError(Exception):
    """Exception raised when authentication fails with GitHub API"""
    def __init__(self, message="GitHub authentication failed", status_code=None):
        self.status_code = status_code
        super().__init__(message)
        
class GitHubRateLimitError(Exception):
    """Exception raised when GitHub API rate limit is exceeded"""
    def __init__(self, message="Rate limit exceeded", rate_limit_info=None, global_exhaustion: bool = False, earliest_reset_timestamp: Optional[float] = None):
        self.rate_limit_info = rate_limit_info if rate_limit_info is not None else {}
        self.global_exhaustion = global_exhaustion
        self.earliest_reset_timestamp = earliest_reset_timestamp
        # Ensure standard rate limit fields are in rate_limit_info if provided separately
        if 'global_exhaustion' not in self.rate_limit_info:
            self.rate_limit_info['global_exhaustion'] = global_exhaustion
        if 'earliest_reset_timestamp' not in self.rate_limit_info and earliest_reset_timestamp is not None:
            self.rate_limit_info['earliest_reset_timestamp'] = earliest_reset_timestamp
        super().__init__(message)

class GitHubClient:
    """Client for interacting with the GitHub API using PyGithub"""
    
    def __init__(self, token: Optional[str] = None, verbose: bool = False, token_manager: Optional[TokenManager] = None, per_page: int = 100):
        """Initialize the GitHub client using PyGithub.
        
        Args:
            token: A GitHub Personal Access Token.
            verbose: Whether to print verbose output.
            token_manager: The token manager (for future multi-token support).
            per_page: Default number of items to fetch per page for paginated PyGithub requests.
        """
        self.verbose = verbose
        self.token_manager = token_manager
        self.per_page = per_page
        self.current_token: Optional[str] = None # Initialize current_token

        if self.token_manager:
            self.current_token = self.token_manager.get_current_token() # Get initial token from manager
            if self.verbose:
                print(f"Using token from manager: {self.current_token[:8] if self.current_token else 'None'}")
        elif token: # Fallback to provided token if no manager
            self.current_token = token
            if self.verbose:
                print(f"Using provided token: {self.current_token[:8] if self.current_token else 'None'}")

        # Configure PyGithub with proper retry and throttling
        self._reinitialize_github_instance()

        self._max_concurrent_requests = 5 
        self.semaphore = asyncio.Semaphore(self._max_concurrent_requests)
        
        # Track problematic endpoints to avoid infinite retry loops
        self._failed_endpoints = {}
        self._max_retry_attempts = 2  # Maximum number of retry attempts per endpoint

    def _reinitialize_github_instance(self):
        """Helper to initialize or re-initialize the github.Github instance."""
        # Create custom retry configuration that uses minimal retries
        # so we can handle rate limits with our own token rotation logic
        retry_config = GithubRetry(
            # Only a few retries
            total=2,                  # Limit to 2 retries
            backoff_factor=0.5,       # Short backoff
            status_forcelist=[500, 502, 504],  # Only retry server errors, not 403
            secondary_rate_wait=10    # Short wait for secondary rate limits
        )
        
        if not self.current_token:
            self.github_instance = Github(
                retry=retry_config, 
                per_page=self.per_page,
                seconds_between_requests=0.25,
                seconds_between_writes=1.0
            )
            if self.verbose: print("🤖 GitHubClient: Initialized PyGithub for unauthenticated access.")
        else:
            self.github_instance = Github(
                self.current_token, 
                retry=retry_config, 
                per_page=self.per_page,
                seconds_between_requests=0.25,
                seconds_between_writes=1.0
            )
            if self.verbose: print(f"🤖 GitHubClient: Initialized PyGithub with token: {self.current_token[:4]}...")

    def update_concurrency_limit(self, limit: int):
        self._max_concurrent_requests = limit
        self.semaphore = asyncio.Semaphore(limit)
    
    async def rotate_token(self) -> bool:
        """Try to rotate to a new token. Returns True if successful."""
        if not self.token_manager or not self.current_token:
            return False
            
        # Use a reasonable default reset time for secondary rate limits (1 minute)
        reset_timestamp = time.time() + 60
        
        new_token = await self.token_manager.handle_token_exhaustion_and_get_next(
            self.current_token,
            reset_timestamp
        )
        
        if new_token and new_token != self.current_token:
            self.current_token = new_token
            self._reinitialize_github_instance()
            return True
        return False
    
    async def _handle_rate_limit_exception(self, e: RateLimitExceededException, endpoint_being_called: str) -> bool:
        """Handles RateLimitExceededException by attempting token rotation and checking global limits."""
        if not self.token_manager or not self.current_token:
            # No token manager or no current token to rotate from, re-raise with basic info
            reset_ts = float(e.headers.get('x-ratelimit-reset', time.time() + 3600))
            rate_info = {"reset": reset_ts, "data": e.data, "headers": dict(e.headers) if e.headers else {}}
            raise GitHubRateLimitError(message=f"Rate limit on {endpoint_being_called}. No token manager for rotation.", rate_limit_info=rate_info)

        if self.verbose: print(f"🔴 RateLimitExceeded for token {self.current_token[:4]}... on {endpoint_being_called}. Attempting to handle...")
        
        # Extract reset time for the failing token
        # PyGithub's RateLimitExceededException has .headers available
        failing_token_reset_timestamp = float(e.headers.get('x-ratelimit-reset', time.time() + 3600)) # Default to 1hr if header missing
        
        new_token = await self.token_manager.handle_token_exhaustion_and_get_next(
            self.current_token, 
            failing_token_reset_timestamp
        )

        if new_token:
            self.current_token = new_token  # UPDATE the current token!
            if self.verbose: print(f"🔄 Successfully switched to new token: {new_token[:4]}... for {endpoint_being_called}")
            self._reinitialize_github_instance() # Use the new self.current_token set by TokenManager
            return True # Indicates successful rotation, caller should retry
        else:
            # No new token available, check if all are exhausted
            if self.verbose: print(f"🤔 No new token available from TokenManager after exhausting {self.current_token[:4]}...")
            is_globally_exhausted, earliest_reset = self.token_manager.get_global_exhaustion_status()
            if is_globally_exhausted:
                msg = f"🚨 All API tokens globally exhausted. Next known reset around: {datetime.fromtimestamp(earliest_reset).strftime('%Y-%m-%d %H:%M:%S') if earliest_reset else 'Unknown'}. Endpoint: {endpoint_being_called}"
                if self.verbose: print(msg)
                raise GitHubRateLimitError(
                    message=msg,
                    rate_limit_info=e.data, # Keep original exception data if useful
                    global_exhaustion=True,
                    earliest_reset_timestamp=earliest_reset
                )
            else:
                # Not globally exhausted, but no alternative token was found (e.g. single token setup, or some other logic path in TM)
                msg = f"Rate limit on {endpoint_being_called} with token {self.current_token[:4]}... No alternative token found or switched. Original error: {e.data.get('message', str(e))}"
                if self.verbose: print(f"⚠️ {msg}")
                # Fallback to raising a normal rate limit error for the current token
                rate_info = {"reset": failing_token_reset_timestamp, "data": e.data, "headers": dict(e.headers) if e.headers else {}}
                raise GitHubRateLimitError(message=msg, rate_limit_info=rate_info)

    async def check_and_rotate_if_needed(self) -> bool:
        """Check if current token is exhausted and rotate if needed. Returns True if rotation occurred."""
        if not self.token_manager or not self.current_token:
            return False
            
        # Check if token is exhausted or low
        rate_limit_data = await self._get_rate_limit_info()
        if 'error' not in rate_limit_data:
            core_limits = rate_limit_data.get('resources', {}).get('core', {})
            remaining = core_limits.get('remaining', 0)
            
            # If remaining is 0 or very low, try to rotate
            if remaining < 100:  # Less than 100 calls remaining
                print(f"⚠️ Current token {self.current_token[:4]}... has only {remaining} calls remaining - trying to rotate")
                
                # Try to get a better token
                new_token = await self.token_manager.get_next_available_token(force_different=True)
                if new_token and new_token != self.current_token:
                    self.current_token = new_token
                    self._reinitialize_github_instance()
                    print(f"🔄 Proactively rotated to token {new_token[:4]}... with more capacity")
                    return True
                    
        return False
    
    async def get_async(self, endpoint: str, params: Dict = None) -> Tuple[int, Dict]:
        # Try to rotate token if it's exhausted before making any request
        await self.check_and_rotate_if_needed()
        
        async with self.semaphore:
            loop = asyncio.get_running_loop()
            try:
                if self.verbose:
                    print(f"📞 PyGithub: Requesting endpoint: {endpoint} with params: {params}")

                params = params or {}
                page_num_1_indexed = params.get("page") 
                page_idx_0_indexed = int(page_num_1_indexed) - 1 if page_num_1_indexed is not None else 0

                # Core endpoints
                if endpoint == "rate_limit":
                    # This call itself consumes a rate limit point if authenticated.
                    # For unauthenticated, it draws from a different pool.
                    rate_limit_obj = await loop.run_in_executor(None, self.github_instance.get_rate_limit)
                    # Update token manager with fresh rate limit data for the current token
                    if self.token_manager and self.current_token:
                        core_limits = rate_limit_obj.core
                        self.token_manager.update_token_rate_limit_data(
                            self.current_token,
                            core_limits.limit,
                            core_limits.remaining,
                            core_limits.reset.timestamp() # PyGithub returns timezone-aware datetime
                        )
                    return 200, self._convert_pygithub_object_to_dict(rate_limit_obj)
                
                # User endpoints
                elif endpoint.startswith("users/"):
                    parts = endpoint.split('/')
                    username = parts[1]
                    user_obj = await loop.run_in_executor(None, self.github_instance.get_user, username)
                    
                    if len(parts) == 2: # /users/{username}
                        return 200, self._convert_pygithub_object_to_dict(user_obj)
                    elif len(parts) == 3 and parts[2] == "repos": # /users/{username}/repos
                        # PyGithub params: type, sort, direction (use keyword arguments)
                        repo_type = params.get("type", NotSet)
                        repo_sort = params.get("sort", NotSet)  
                        repo_direction = params.get("direction", NotSet)
                        paginated_list = await loop.run_in_executor(None, partial(user_obj.get_repos, type=repo_type, sort=repo_sort, direction=repo_direction))
                        page_items = await loop.run_in_executor(None, paginated_list.get_page, page_idx_0_indexed)
                        return 200, [self._convert_pygithub_object_to_dict(item) for item in page_items]
                    elif len(parts) == 3 and parts[2] == "events": # /users/{username}/events
                        paginated_list = await loop.run_in_executor(None, user_obj.get_events)
                        page_items = await loop.run_in_executor(None, paginated_list.get_page, page_idx_0_indexed)
                        return 200, [self._convert_pygithub_object_to_dict(item) for item in page_items]
                
                # Repository endpoints
                elif endpoint.startswith("repos/"):
                    path_parts = endpoint.split('/')
                    owner, repo_name_str = path_parts[1], path_parts[2]
                    repo_full_name = f"{owner}/{repo_name_str}"
                    repo_obj = await loop.run_in_executor(None, self.github_instance.get_repo, repo_full_name)

                    if len(path_parts) == 3: # /repos/{owner}/{repo}
                        return 200, self._convert_pygithub_object_to_dict(repo_obj)
                    elif len(path_parts) > 3:
                        sub_resource = path_parts[3]
                        if sub_resource == "pulls": # /repos/{owner}/{repo}/pulls
                            pr_state = params.get("state", "closed")
                            pr_sort = params.get("sort", "updated")
                            pr_direction = params.get("direction", "desc")
                            pr_base = params.get("base", NotSet) # optional filter by base branch
                            pr_head = params.get("head", NotSet) # optional filter by head user/branch
                            # Use keyword arguments for PyGithub get_pulls method
                            paginated_list = await loop.run_in_executor(None, partial(repo_obj.get_pulls, state=pr_state, sort=pr_sort, direction=pr_direction, base=pr_base, head=pr_head))
                            page_items = await loop.run_in_executor(None, paginated_list.get_page, page_idx_0_indexed)
                            return 200, [self._convert_pygithub_object_to_dict(item) for item in page_items]
                        elif sub_resource == "forks": # /repos/{owner}/{repo}/forks
                            # PyGithub's get_forks() doesn't accept sort parameter - it returns all forks
                            # The sort parameter would need to be handled on our side after fetching
                            paginated_list = await loop.run_in_executor(None, repo_obj.get_forks)
                            page_items = await loop.run_in_executor(None, paginated_list.get_page, page_idx_0_indexed)
                            return 200, [self._convert_pygithub_object_to_dict(item) for item in page_items]
                        elif sub_resource == "languages": # /repos/{owner}/{repo}/languages
                            languages_dict = await loop.run_in_executor(None, repo_obj.get_languages)
                            return 200, languages_dict # This is already a dict
                        elif sub_resource == "contents": # /repos/{owner}/{repo}/contents/{path...}
                            content_path = "/".join(path_parts[4:])
                            ref = params.get("ref", NotSet) # Optional commit/branch/tag
                            contents = await loop.run_in_executor(None, partial(repo_obj.get_contents, content_path, ref=ref))
                            if isinstance(contents, list): # It's a list if path is a directory
                                return 200, [self._convert_pygithub_object_to_dict(c) for c in contents]
                            else: # It's a single ContentFile if path is a file
                                return 200, self._convert_pygithub_object_to_dict(contents)
                else:
                    if self.verbose: print(f"⚠️ PyGithubClient: Endpoint '{endpoint}' not explicitly mapped yet.")
                    return 501, {"message": f"Endpoint not implemented: {endpoint}"}

            except RateLimitExceededException as e:
                if await self._handle_rate_limit_exception(e, endpoint):
                    if self.verbose: print(f"↪️ Retrying {endpoint} after successful token rotation/handling.")
                    return await self.get_async(endpoint, params) # Retry the call
                else:
                    # This else block should ideally not be reached if _handle_rate_limit_exception always raises or returns True for retry.
                    # If it somehow returns False without raising, it implies an unhandled state.
                    # For safety, re-raise the original error, though the logic in _handle_rate_limit_exception
                    # is designed to always raise if a retry isn't possible.
                    if self.verbose: print(f"⚠️ Rate limit handling for {endpoint} did not lead to a retry. Re-raising original error.")
                    raise # Re-raise original if not handled for retry (should be covered by _handle_rate_limit_exception)
            
            except BadCredentialsException as e:
                if self.verbose: print(f"🔴 PyGithub BadCredentialsException for {endpoint}: {e.status}, {e.data}")
                raise GitHubAuthError(message=f"Bad Credentials: {e.data.get('message', str(e))}", status_code=e.status)
            
            except UnknownObjectException as e: 
                if self.verbose: print(f"❓ PyGithub UnknownObjectException (404) for {endpoint}: {e.status}, {e.data}")
                return e.status, {"message": e.data.get('message', str(e)), "documentation_url": e.data.get("documentation_url")}
            
            except GithubException as e: 
                if self.verbose: print(f"🔴 PyGithub GithubException for {endpoint}: {e.status}, {e.data}")
                # Check for secondary rate limit message
                msg_lower = str(e.data.get('message', '')).lower()
                if "secondary rate limit" in msg_lower or "abuse detection" in msg_lower or e.status == 403:
                    # Check if we've tried this endpoint too many times already
                    retry_count = self._failed_endpoints.get(endpoint, 0)
                    self._failed_endpoints[endpoint] = retry_count + 1
                    
                    if retry_count >= self._max_retry_attempts:
                        print(f"\n⚠️ Endpoint {endpoint} has failed {retry_count+1} times with 403 errors - skipping")
                        return 403, {"message": f"Skipping endpoint after {retry_count+1} 403 errors", "data": e.data}
                    
                    # For 403 errors, check all tokens' status to give user clear feedback
                    if self.token_manager and e.status == 403:
                        print("\n⚠️ Received 403 Forbidden - checking all tokens' status...")
                        status_report = await self.token_manager.check_all_tokens_status(self)
                        
                        if status_report['all_exhausted']:
                            # All tokens are exhausted
                            print("\n💾 All tokens exhausted - see status above")
                            raise GitHubRateLimitError(
                                message="All tokens exhausted - see status above",
                                rate_limit_info={"all_exhausted": True, "earliest_reset": status_report['earliest_reset']},
                                global_exhaustion=True,
                                earliest_reset_timestamp=status_report['earliest_reset']
                            )
                        else:
                            # IMPROVED FIX: Try ALL tokens before backing off
                            print(f"🔄 Attempting token rotation after 403 error for {endpoint}")
                            
                            # Force rotation to a different token
                            new_token = await self.token_manager.get_next_available_token(force_different=True)
                            if new_token and new_token != self.current_token:
                                # Successfully found a different token
                                old_token = self.current_token
                                self.current_token = new_token
                                self._reinitialize_github_instance()
                                print(f"✅ Rotated from token {old_token[:4]}... to {new_token[:4]}...")
                                
                                # Try the request again with the new token
                                print(f"↪️ Retrying request to {endpoint} with new token")
                                return await self.get_async(endpoint, params)
                            else:
                                # Could not find a different token - apply short backoff and retry with current token
                                backoff_time = 10  # Short 10 second backoff
                                print(f"\n⏱️ All tokens have been tried, applying {backoff_time}s backoff before retrying")
                                await asyncio.sleep(backoff_time)
                                
                                # After backoff, reinitialize the client to reset any internal rate limit state
                                self._reinitialize_github_instance()
                                print(f"↪️ Retrying request to {endpoint} after backoff")
                                return await self.get_async(endpoint, params)
                    elif self.token_manager:
                        # Try ALL tokens before backing off
                        print(f"🔄 Attempting token rotation after secondary rate limit for {endpoint}")
                        
                        # Force rotation to a different token
                        new_token = await self.token_manager.get_next_available_token(force_different=True)
                        if new_token and new_token != self.current_token:
                            # Successfully found a different token
                            old_token = self.current_token
                            self.current_token = new_token
                            self._reinitialize_github_instance()
                            print(f"✅ Rotated from token {old_token[:4]}... to {new_token[:4]}...")
                            
                            # Try the request again with the new token
                            print(f"↪️ Retrying request to {endpoint} with new token")
                            return await self.get_async(endpoint, params)
                        else:
                            # Could not find a different token - apply short backoff and retry with current token
                            backoff_time = 10  # Short 10 second backoff
                            print(f"\n⏱️ All tokens have been tried, applying {backoff_time}s backoff before retrying")
                            await asyncio.sleep(backoff_time)
                            
                            # After backoff, reinitialize the client to reset any internal rate limit state
                            self._reinitialize_github_instance()
                            print(f"↪️ Retrying request to {endpoint} after backoff")
                            return await self.get_async(endpoint, params)
                    
                    rate_limit_info_dict = {"reset": time.time() + 60, "data": e.data, "secondary": True, "headers": dict(e.headers) if e.headers else {}}
                    raise GitHubRateLimitError(message=f"Secondary Rate Limit: {e.data.get('message', str(e))}", rate_limit_info=rate_limit_info_dict)
                return e.status, {"message": e.data.get('message', str(e)), "data": e.data}
                
            except Exception as e:
                if self.verbose: print(f"❌ Unexpected error in PyGithubClient.get_async for {endpoint}: {e}")
                return 500, {"message": str(e)}

    def _convert_pygithub_object_to_dict(self, obj: Any) -> Dict[str, Any]:
        if obj is None: return {}
        if isinstance(obj, dict): return obj # Already a dict (e.g. get_languages)

        # Check for RateLimit object first, before _rawData
        if isinstance(obj, object) and obj.__class__.__name__ == 'RateLimit': 
            return {
                "resources": {
                    "core": {
                        "limit": obj.core.limit, "remaining": obj.core.remaining,
                        "reset": int(obj.core.reset.timestamp()), "used": obj.core.used
                    },
                    "search": {
                        "limit": obj.search.limit, "remaining": obj.search.remaining,
                        "reset": int(obj.search.reset.timestamp()), "used": obj.search.used
                    }
                },
                "rate": { 
                    "limit": obj.core.limit, "remaining": obj.core.remaining,
                    "reset": int(obj.core.reset.timestamp()), "used": obj.core.used
                }
            }

        data = {}
        if hasattr(obj, '_rawData'): 
            data = obj._rawData.copy() 
            return data 
        
        if isinstance(obj, ContentFile):
            # ContentFile needs special handling as _rawData might not be complete for our needs
            return {
                "type": obj.type,
                "encoding": obj.encoding,
                "size": obj.size,
                "name": obj.name,
                "path": obj.path,
                "content": obj.content, # This is base64 encoded string
                "sha": obj.sha,
                "url": obj.url,
                "git_url": obj.git_url,
                "html_url": obj.html_url,
                "download_url": obj.download_url,
                "_links": {"self": obj.url, "git": obj.git_url, "html": obj.html_url}
            }

        if not data: 
            if self.verbose:
                print(f"⚠️ Could not find _rawData for {type(obj)}. Returning placeholder dict.")
            # Extremely basic fallback, not recommended for complex objects.
            # This won't be sufficient for most objects if _rawData is missing.
            return {'val': str(obj)} 

        return data 

    async def _get_rate_limit_info(self, token: str = None) -> Dict:
        try:
            if self.verbose:
                print(f"  📊 Checking rate limit for token: {self.current_token[:8] if self.current_token else 'None'}...")
            rate_limit_obj = await asyncio.get_running_loop().run_in_executor(None, self.github_instance.get_rate_limit)
            result = self._convert_pygithub_object_to_dict(rate_limit_obj)
            if self.verbose:
                core = result.get('resources', {}).get('core', {})
                print(f"  ✅ Rate limit check successful: {core.get('remaining', 0)}/{core.get('limit', 5000)}")
            return result
        except BadCredentialsException as e:
            if self.verbose: 
                print(f"  🔐 Bad credentials for rate limit check: {e.data}")
            return {"error": f"Bad credentials: {str(e)}"}
        except Exception as e:
            if self.verbose: 
                print(f"  ❌ Error getting rate limit info: {type(e).__name__} - {str(e)}")
            return {"error": f"{type(e).__name__}: {str(e)}"}
            
    async def close_session(self):
        if self.verbose: print("✅ PyGithub client does not require explicit session closing.")
        pass

    async def get_user_pygithub_object(self, username: str) -> Optional['github.NamedUser']:
        """Fetches the raw PyGithub NamedUser object."""
        # Try to rotate token if it's exhausted before making any request
        await self.check_and_rotate_if_needed()
        
        async with self.semaphore:
            loop = asyncio.get_running_loop()
            try:
                if self.verbose:
                    print(f"👤 PyGithub: Fetching NamedUser object for: {username}")
                user_obj = await loop.run_in_executor(None, self.github_instance.get_user, username)
                # After successful call, update rate limit info for the current token
                if self.token_manager and self.current_token:
                    try:
                        # Fetching full rate limit data after every call might be too much.
                        # PyGithub objects don't easily expose last response headers.
                        # Relying on RateLimitExceededException for exhaustion and periodic checks for now.
                        # For a more proactive update, one might call: 
                        # limits = await loop.run_in_executor(None, self.github_instance.get_rate_limit)
                        # self.token_manager.update_token_rate_limit_data(self.current_token, limits.core.limit, ...)
                        pass # Placeholder for potential future proactive update
                    except Exception as rl_update_err:
                        if self.verbose: print(f"⚠️ Error updating rate limit post-fetch: {rl_update_err}")
                return user_obj
            except RateLimitExceededException as e:
                if await self._handle_rate_limit_exception(e, f"users/{username}"):
                    if self.verbose: print(f"↪️ Retrying get_user_pygithub_object for {username} after successful token rotation/handling.")
                    return await self.get_user_pygithub_object(username) # Retry the call
                else:
                    # As in get_async, this path should ideally not be hit.
                    if self.verbose: print(f"⚠️ Rate limit handling for get_user_pygithub_object({username}) did not lead to a retry. Re-raising original error.")
                    raise # Re-raise original if not handled for retry
            except BadCredentialsException as e:
                if self.verbose: print(f"🔴 PyGithub BadCredentialsException for user {username}: {e.status}, {e.data}")
                raise GitHubAuthError(message=f"Bad Credentials fetching user object: {e.data.get('message', str(e))}", status_code=e.status)
            except UnknownObjectException as e: 
                if self.verbose: print(f"❓ PyGithub UnknownObjectException (404) for user {username}: {e.status}, {e.data}")
                return None # User not found
            except GithubException as e: 
                if self.verbose: print(f"🔴 PyGithub GithubException for user {username}: {e.status}, {e.data}")
                msg_lower = str(e.data.get('message', '')).lower()
                if "secondary rate limit" in msg_lower or "abuse detection" in msg_lower or e.status == 403:
                    # Check if we've tried this username too many times already
                    endpoint_key = f"user/{username}"
                    retry_count = self._failed_endpoints.get(endpoint_key, 0)
                    self._failed_endpoints[endpoint_key] = retry_count + 1
                    
                    if retry_count >= self._max_retry_attempts:
                        print(f"\n⚠️ User fetch for {username} has failed {retry_count+1} times with 403 errors - skipping")
                        return None
                    
                    # For 403 errors, check all tokens' status to give user clear feedback
                    if self.token_manager and e.status == 403:
                        print("\n⚠️ Received 403 Forbidden - checking all tokens' status...")
                        status_report = await self.token_manager.check_all_tokens_status(self)
                        
                        if status_report['all_exhausted']:
                            # All tokens are exhausted
                            print("\n💾 All tokens exhausted - see status above")
                            raise GitHubRateLimitError(
                                message="All tokens exhausted - see status above",
                                rate_limit_info={"all_exhausted": True, "earliest_reset": status_report['earliest_reset']},
                                global_exhaustion=True,
                                earliest_reset_timestamp=status_report['earliest_reset']
                            )
                        else:
                            # IMPROVED FIX: Try ALL tokens before backing off
                            print(f"🔄 Attempting token rotation after 403 error for user {username}")
                            
                            # Force rotation to a different token
                            new_token = await self.token_manager.get_next_available_token(force_different=True)
                            if new_token and new_token != self.current_token:
                                # Successfully found a different token
                                old_token = self.current_token
                                self.current_token = new_token
                                self._reinitialize_github_instance()
                                print(f"✅ Rotated from token {old_token[:4]}... to {new_token[:4]}...")
                                
                                # Try the request again with the new token
                                print(f"↪️ Retrying user fetch for {username} with new token")
                                return await self.get_user_pygithub_object(username)
                            else:
                                # Could not find a different token - apply short backoff and retry
                                backoff_time = 10  # Short 10 second backoff
                                print(f"\n⏱️ All tokens have been tried, applying {backoff_time}s backoff before retrying")
                                await asyncio.sleep(backoff_time)
                                
                                # After backoff, reinitialize the client to reset any internal rate limit state
                                self._reinitialize_github_instance()
                                print(f"↪️ Retrying user fetch for {username} after backoff")
                                return await self.get_user_pygithub_object(username)
                    elif self.token_manager:
                        # Try ALL tokens before backing off
                        print(f"🔄 Attempting token rotation after secondary rate limit for user {username}")
                        
                        # Force rotation to a different token
                        new_token = await self.token_manager.get_next_available_token(force_different=True)
                        if new_token and new_token != self.current_token:
                            # Successfully found a different token
                            old_token = self.current_token
                            self.current_token = new_token
                            self._reinitialize_github_instance()
                            print(f"✅ Rotated from token {old_token[:4]}... to {new_token[:4]}...")
                            
                            # Try the request again with the new token
                            print(f"↪️ Retrying user fetch for {username} with new token")
                            return await self.get_user_pygithub_object(username)
                        else:
                            # Could not find a different token - apply short backoff and retry
                            backoff_time = 10  # Short 10 second backoff
                            print(f"\n⏱️ All tokens have been tried, applying {backoff_time}s backoff before retrying")
                            await asyncio.sleep(backoff_time)
                            
                            # After backoff, reinitialize the client to reset any internal rate limit state
                            self._reinitialize_github_instance()
                            print(f"↪️ Retrying user fetch for {username} after backoff")
                            return await self.get_user_pygithub_object(username)
                    rate_limit_info_dict = {"reset": time.time() + 60, "data": e.data, "secondary": True, "headers": dict(e.headers) if e.headers else {}}
                    raise GitHubRateLimitError(message=f"Secondary Rate Limit fetching user object: {e.data.get('message', str(e))}", rate_limit_info=rate_limit_info_dict)
                # For other GithubException, we might not want to return None, but raise an error
                # For now, let's consider it a failure to fetch user, but this could be more specific
                print(f"❌ GitHubException (status {e.status}) fetching user {username}, returning None. Message: {e.data.get('message', str(e))}")
                return None 
            except Exception as e:
                if self.verbose: print(f"❌ Unexpected error fetching user object {username}: {type(e).__name__} - {str(e)}")
                return None

# The old SessionPool and extensive manual rate limit handling in client.get()
# are largely superseded by PyGithub's own mechanisms and the proposed wrapper logic.
# The TokenManager will need to be more tightly integrated if multi-token rotation
# is to be preserved robustly with PyGithub instances. 