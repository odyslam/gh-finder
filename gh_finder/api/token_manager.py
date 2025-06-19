"""
GitHub token management with rotation support
"""

from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Tuple, Any
import asyncio
import time

class TokenManager:
    """Manages GitHub API tokens and rate limits"""
    
    def __init__(self, tokens: List[str], verbose: bool = False):
        """Initialize the token manager
        
        Args:
            tokens: List of GitHub tokens
            verbose: Whether to print verbose output
        """
        self.tokens_queue = deque(tokens)  # Use a deque for easier rotation
        self.verbose = verbose
        
        # Comprehensive state for each token
        self.token_states: Dict[str, Dict[str, Any]] = {}
        for token_str in tokens:
            # Skip empty tokens or tokens that are too short (must be at least 10 chars)
            if not token_str or len(token_str) < 10:
                if self.verbose:
                    print(f"⚠️ Skipping invalid token (too short or empty): {token_str[:4] if token_str else 'empty'}")
                continue
                
            # Init the token state
            self._init_token_state(token_str)

        # Initialize current token (if any valid tokens exist)
        self.current_token: Optional[str] = self.tokens_queue[0] if self.tokens_queue else None
        
        self.lock = asyncio.Lock()  # For synchronizing access to shared state if needed by client
        
        if self.verbose:
            print(f"TokenManager initialized with {len(self.tokens_queue)} tokens. Current: {self.current_token[:4] if self.current_token else 'None'}...")
            
    def _init_token_state(self, token_str: str):
        """Initializes or re-initializes the state for a given token string."""
        if token_str not in self.token_states:
            self.token_states[token_str] = {
                'limit': 5000,             # Default, will be updated from API
                'remaining': -1,           # -1 indicates "not yet checked", will be updated from API
                'reset_timestamp': 0.0,    # Unix timestamp
                'is_globally_exhausted_until': 0.0, # Timestamp until which this token is considered unusable due to global rate limit
                'consecutive_failures': 0 # For future use, e.g. detecting bad tokens
            }

    def add_token(self, token_str: str) -> bool:
        """Add a new token to the manager if it doesn't already exist."""
        if token_str and token_str not in self.token_states:
            self.tokens_queue.append(token_str)
            self._init_token_state(token_str)
            if not self.current_token: # If no token was current (e.g. initialized with empty list)
                self.current_token = token_str
            if self.verbose: print(f"Added new token: {token_str[:4]}...")
            return True
        return False

    def get_current_token(self) -> Optional[str]:
        """Get the currently active token."""
        return self.current_token

    def update_token_rate_limit_data(self, token: str, limit: int, remaining: int, reset_timestamp: float):
        """Called by GitHubClient to provide the latest rate limit data from headers."""
        if token in self.token_states:
            self.token_states[token]['limit'] = limit
            self.token_states[token]['remaining'] = remaining
            self.token_states[token]['reset_timestamp'] = reset_timestamp
            # If remaining is very low, it might be close to exhaustion, but is_globally_exhausted_until is the key
            if remaining < 5 and self.verbose: # Arbitrary low threshold for warning
                 print(f"⚠️ Token {token[:4]}... has only {remaining} requests remaining.")
        elif self.verbose:
            print(f"❓ Attempted to update rate limit for unknown token: {token[:4]}...")
            
    def mark_token_globally_exhausted(self, token: str, actual_reset_timestamp: float):
        """
        Marks a token as unusable due to hitting a rate limit that PyGithub's retries couldn't overcome.
        This implies a more persistent rate limit state for this token.
        """
        if token in self.token_states:
            self.token_states[token]['is_globally_exhausted_until'] = actual_reset_timestamp
            self.token_states[token]['remaining'] = 0 # Assume 0 remaining when exhausted
            if self.verbose:
                reset_dt = datetime.fromtimestamp(actual_reset_timestamp)
                print(f"🔴 Token {token[:4]}... marked globally exhausted until {reset_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        elif self.verbose:
            print(f"❓ Attempted to mark unknown token as globally exhausted: {token[:4]}...")

    async def get_next_available_token(self, force_different: bool = False, current_token: Optional[str] = None) -> Optional[str]:
        """
        Finds the next best token that is not currently globally exhausted OR whose exhaustion period has passed.
        This method does NOT rotate self.current_token directly. It only suggests a candidate.
        
        Args:
            force_different: If True, force picking a different token than the current one
            current_token: Current token to avoid if force_different is True (defaults to self.current_token)
        """
        async with self.lock: # Ensure consistent state reading
            now = time.time()
            best_candidate: Optional[str] = None
            highest_remaining = -1
            token_to_avoid = current_token if current_token else self.current_token

            # First try to find a token different from the current one if requested
            if force_different and token_to_avoid:
                print(f"  🔍 Actively looking for a token different from {token_to_avoid[:4]}...")
                
                # Specifically look for tokens different from the current one
                for token_str in list(self.tokens_queue):
                    if token_str == token_to_avoid:
                        continue  # Skip current token
                        
                    state = self.token_states.get(token_str)
                    if not state:
                        continue

                    # If token was exhausted, check if its reset time has passed
                    if state['is_globally_exhausted_until'] > now:
                        if self.verbose: print(f"  Token {token_str[:4]}... still exhausted until {datetime.fromtimestamp(state['is_globally_exhausted_until']).strftime('%H:%M:%S')}")
                        continue # Skip this token, it's still cooling down
                    
                    # Found a non-exhausted token different from current
                    print(f"  ✅ Found alternative token {token_str[:4]}... (Remaining: {state['remaining']})")
                    return token_str

            # Fallback to normal search if no alternative token found or force_different=False
            for token_str in list(self.tokens_queue):
                # Skip current token if we're forcing a different one
                if force_different and token_str == token_to_avoid:
                    continue
                    
                state = self.token_states.get(token_str)
                if not state:
                    continue

                # If token was exhausted, check if its reset time has passed
                if state['is_globally_exhausted_until'] > now:
                    if self.verbose: print(f"  Token {token_str[:4]}... still exhausted until {datetime.fromtimestamp(state['is_globally_exhausted_until']).strftime('%H:%M:%S')}")
                    continue # Skip this token, it's still cooling down

                # Token is not (or no longer) globally exhausted, consider it based on remaining requests
                if state['remaining'] > highest_remaining:
                    highest_remaining = state['remaining']
                    best_candidate = token_str
                elif best_candidate is None: # If all available tokens have 0 or unknown remaining, pick the first one
                    best_candidate = token_str

            if self.verbose and best_candidate:
                print(f"  Next best token candidate: {best_candidate[:4]}... (Remaining: {self.token_states[best_candidate]['remaining']})")
            elif self.verbose:
                print("  No suitable next token candidate found (all might be exhausted).")
                
            # Last resort: if force_different but we couldn't find a different token,
            # just return the current one (better than returning None)
            if force_different and not best_candidate and token_to_avoid:
                if self.token_states.get(token_to_avoid, {}).get('is_globally_exhausted_until', 0) <= now:
                    print(f"  ⚠️ No alternative tokens found, falling back to current token")
                    return token_to_avoid
                
            return best_candidate

    def switch_to_token(self, new_token: str) -> bool:
        """Sets the new_token as the current_token if it's managed by the TokenManager."""
        if new_token in self.token_states:
            if self.current_token == new_token and self.verbose:
                 print(f"Token {new_token[:4]}... is already current.")
                 return True # No change needed, but successful in a way
            
            self.current_token = new_token
            # Move the new current token to the front of the deque for logical ordering if desired,
            # though self.current_token is the source of truth now for the client.
            if new_token in self.tokens_queue:
                self.tokens_queue.remove(new_token)
            self.tokens_queue.appendleft(new_token)
            
            if self.verbose:
                print(f"🔄 Switched current token to: {self.current_token[:4]}...")
            return True
        if self.verbose:
            print(f"⚠️ Attempted to switch to an unmanaged token: {new_token[:4]}...")
        return False

    def get_global_exhaustion_status(self) -> Tuple[bool, Optional[float]]:
        """
        Checks if all managed tokens are currently marked as globally exhausted 
        and their reset times are still in the future.

        Returns:
            Tuple[bool, Optional[float]]: (True_if_all_exhausted, earliest_next_reset_timestamp_if_exhausted_else_None)
        """
        now = time.time()
        all_truly_exhausted = True
        min_future_reset_timestamp: Optional[float] = None
        any_not_checked = False

        if not self.token_states: # No tokens to be exhausted
            return False, None

        for token_str, state in self.token_states.items():
            # If token hasn't been checked yet (remaining == -1), we can't say it's exhausted
            if state['remaining'] == -1:
                any_not_checked = True
                all_truly_exhausted = False
                break
                
            if state['is_globally_exhausted_until'] <= now :
                # This token is not currently considered exhausted (its time passed or was never set high)
                all_truly_exhausted = False
                break 
            else: # Token is exhausted, and reset time is in the future
                if min_future_reset_timestamp is None or state['is_globally_exhausted_until'] < min_future_reset_timestamp:
                    min_future_reset_timestamp = state['is_globally_exhausted_until']
        
        # Don't report as exhausted if we haven't checked all tokens yet
        if any_not_checked:
            return False, None
            
        if all_truly_exhausted:
            if self.verbose: print(f"🚨 All tokens appear globally exhausted. Earliest known reset at: {datetime.fromtimestamp(min_future_reset_timestamp).strftime('%Y-%m-%d %H:%M:%S') if min_future_reset_timestamp else 'N/A'}")
            return True, min_future_reset_timestamp
        else:
            return False, None

    def get_token_count(self) -> int:
        return len(self.token_states)

    # --- Methods to be reviewed/removed/refactored from old TokenManager ---
    # get_token(), add_request(), update_limits(), mark_rate_limited() (replaced by mark_token_globally_exhausted)
    # get_rate_limit_status(), get_token_async(), get_auth_header()
    # update_rate_limit(), update_token_usage(), find_best_token()
    # validate_all_tokens(), _validate_single_token(), get_tokens_status()
    # The old rotate_token() will be effectively replaced by logic in GitHubClient
    # calling mark_token_globally_exhausted and then get_next_available_token + switch_to_token.
    
    # Simplified rotate_token for GitHubClient's direct use, primarily for signaling exhaustion
    # and attempting to get a new one.
    async def handle_token_exhaustion_and_get_next(self, exhausted_token: str, reset_timestamp: float) -> Optional[str]:
        """
        Marks the given token as exhausted and tries to find and set a new current token.
        Returns the new current token if successful, or None if no other token is available.
        This should be called by GitHubClient when a RateLimitExceededException is definitively hit for the current_token.
        """
        async with self.lock:
            if self.verbose: print(f"Handling exhaustion for token {exhausted_token[:4]}...")
            self.mark_token_globally_exhausted(exhausted_token, reset_timestamp)
            
            # Try to find a new token that isn't the one just exhausted
            # and isn't itself exhausted.
            # The `get_next_available_token` method already considers exhaustion times.
            
            candidate_token = await self.get_next_available_token()
            
            if candidate_token and candidate_token != exhausted_token:
                if self.switch_to_token(candidate_token):
                    return candidate_token
            elif candidate_token and candidate_token == exhausted_token:
                 if self.verbose: print(f"  Candidate token {candidate_token[:4]} is the same as exhausted one. Checking others...")
                 # This case means get_next_available_token found only the current one (now marked exhausted)
                 # or it's the only token. We need to re-evaluate.
                 # Let's try iterating through the queue to find a *different* one.
                 for i in range(len(self.tokens_queue)):
                     potential_next = self.tokens_queue[0]
                     self.tokens_queue.rotate(-1) # Move to next
                     if potential_next != exhausted_token:
                         state = self.token_states.get(potential_next)
                         if state and state['is_globally_exhausted_until'] <= time.time():
                            if self.switch_to_token(potential_next):
                                return potential_next
                 # If loop finishes, no other non-exhausted token was found.
                 if self.verbose: print(f"  No alternative non-exhausted token found after checking queue for {exhausted_token[:4]}.")


            # If no other token was found or switched to, check for global exhaustion.
            all_exhausted, _ = self.get_global_exhaustion_status()
            if all_exhausted:
                if self.verbose: print(f"  All tokens are globally exhausted. Cannot switch from {exhausted_token[:4]}.")
                # Keep current_token as the one that just failed, client will handle global exhaustion.
                self.current_token = exhausted_token 
                return None 

            # If not all exhausted, but chosen candidate was the same and no other alternatives worked,
            # this implies a more complex state, or single token scenario.
            # For now, if candidate_token exists and is different, it should have been switched.
            # If candidate_token is None, it means get_next_available_token found nothing usable.
            if not candidate_token:
                 if self.verbose: print(f"  No candidate token found by get_next_available_token after exhausting {exhausted_token[:4]}.")
                 self.current_token = exhausted_token # Reaffirm current token if no switch.
                 return None


            # Fallback: if we reached here, something is complex.
            # Re-set current to the exhausted one if no switch occurred. Client will handle.
            if self.current_token != exhausted_token and exhausted_token in self.token_states:
                 # This path should ideally not be hit if logic above is complete
                 # For safety, if self.current_token was somehow changed to something else
                 # but we didn't successfully return a *new* token, indicate no *new* token is available.
                 pass

            if self.current_token == exhausted_token: # If no switch happened
                 if self.verbose: print(f"  Unable to switch away from exhausted token {exhausted_token[:4]} or it's the only one.")
                 return None # Indicate no *new* token is available

            return self.current_token # Should be the newly switched token if successful 
    
    async def check_all_tokens_status(self, github_client) -> Dict[str, Any]:
        """
        Check the actual rate limit status of all tokens by querying the GitHub API.
        Returns a comprehensive status report.
        
        Args:
            github_client: The GitHubClient instance to use for checking rate limits
            
        Returns:
            Dict with status information for all tokens
        """
        from datetime import datetime
        import time
        
        all_tokens_status = {}
        current_time = time.time()
        earliest_reset = None
        any_available = False
        
        print("\n" + "="*60)
        print("🔍 CHECKING ALL TOKENS RATE LIMIT STATUS")
        print("="*60)
        
        for i, token in enumerate(self.tokens_queue):
            # Temporarily switch to this token to check its rate limit
            original_token = github_client.current_token
            github_client.current_token = token
            github_client._reinitialize_github_instance()
            
            try:
                # Get rate limit for this token
                rate_limit_data = await github_client._get_rate_limit_info(token)
                
                if 'error' not in rate_limit_data:
                    core_limits = rate_limit_data.get('resources', {}).get('core', {})
                    remaining = core_limits.get('remaining', 0)
                    limit = core_limits.get('limit', 5000)
                    reset_timestamp = core_limits.get('reset', 0)
                    
                    # Update our internal state
                    self.update_token_rate_limit_data(token, limit, remaining, reset_timestamp)
                    
                    # Check if token is available
                    is_available = remaining > 0
                    if is_available:
                        any_available = True
                    
                    # Track earliest reset time
                    if not is_available and (earliest_reset is None or reset_timestamp < earliest_reset):
                        earliest_reset = reset_timestamp
                    
                    # Format reset time
                    if reset_timestamp > current_time:
                        reset_dt = datetime.fromtimestamp(reset_timestamp)
                        reset_str = reset_dt.strftime('%Y-%m-%d %H:%M:%S')
                        time_until_reset = reset_timestamp - current_time
                        if time_until_reset < 3600:
                            time_until_str = f"{int(time_until_reset / 60)} minutes"
                        else:
                            time_until_str = f"{int(time_until_reset / 3600)} hours {int((time_until_reset % 3600) / 60)} minutes"
                    else:
                        reset_str = "Already reset"
                        time_until_str = "Available now"
                    
                    # Store status
                    all_tokens_status[token] = {
                        'remaining': remaining,
                        'limit': limit,
                        'reset_timestamp': reset_timestamp,
                        'is_available': is_available,
                        'reset_str': reset_str,
                        'time_until_str': time_until_str
                    }
                    
                    # Print status
                    status_emoji = "✅" if is_available else "❌"
                    print(f"\nToken {i+1}: {token[:8]}...")
                    print(f"  {status_emoji} Remaining: {remaining}/{limit}")
                    print(f"  ⏰ Reset: {reset_str} ({time_until_str})")
                    
                    # Also check secondary rate limit status if available
                    search_limits = rate_limit_data.get('resources', {}).get('search', {})
                    if search_limits:
                        search_remaining = search_limits.get('remaining', 0)
                        search_limit = search_limits.get('limit', 30)
                        print(f"  🔍 Search API: {search_remaining}/{search_limit}")
                    
                else:
                    print(f"\nToken {i+1}: {token[:8]}...")
                    print(f"  ❌ Error checking rate limit: {rate_limit_data.get('error')}")
                    all_tokens_status[token] = {
                        'error': rate_limit_data.get('error'),
                        'is_available': False
                    }
                    
            except Exception as e:
                print(f"\nToken {i+1}: {token[:8]}...")
                print(f"  ❌ Error checking rate limit: {str(e)}")
                all_tokens_status[token] = {
                    'error': str(e),
                    'is_available': False
                }
        
        # Restore original token
        github_client.current_token = original_token
        github_client._reinitialize_github_instance()
        
        # Summary
        print("\n" + "="*60)
        if any_available:
            available_count = sum(1 for s in all_tokens_status.values() if s.get('is_available', False))
            print(f"✅ {available_count} token(s) have remaining API calls")
            print("💡 The tool should be able to continue with available tokens")
        else:
            print("❌ ALL TOKENS ARE EXHAUSTED")
            if earliest_reset:
                reset_dt = datetime.fromtimestamp(earliest_reset)
                reset_str = reset_dt.strftime('%Y-%m-%d %H:%M:%S')
                time_until_reset = earliest_reset - current_time
                if time_until_reset < 3600:
                    time_until_str = f"{int(time_until_reset / 60)} minutes"
                else:
                    time_until_str = f"{int(time_until_reset / 3600)} hours {int((time_until_reset % 3600) / 60)} minutes"
                
                print(f"\n⏰ EARLIEST TOKEN RESET: {reset_str}")
                print(f"⏳ TIME TO WAIT: {time_until_str}")
                print(f"\n💡 Resume command for then:")
                print(f"   ./run.py --resume latest --config YOUR_CONFIG")
            else:
                print("\n⚠️ Unable to determine when tokens will reset")
        
        print("="*60 + "\n")
        
        return {
            'tokens_status': all_tokens_status,
            'any_available': any_available,
            'earliest_reset': earliest_reset,
            'all_exhausted': not any_available
        }
    
    async def print_compact_status(self, github_client) -> None:
        """Print a compact summary of all tokens' status"""
        from datetime import datetime
        import time
        
        current_time = time.time()
        statuses = []
        
        for i, token in enumerate(self.tokens_queue):
            # Temporarily switch to this token to check its rate limit
            original_token = github_client.current_token
            github_client.current_token = token
            github_client._reinitialize_github_instance()
            
            try:
                # Get rate limit for this token
                rate_limit_data = await github_client._get_rate_limit_info(token)
                
                if 'error' not in rate_limit_data:
                    core_limits = rate_limit_data.get('resources', {}).get('core', {})
                    remaining = core_limits.get('remaining', 0)
                    limit = core_limits.get('limit', 5000)
                    reset_timestamp = core_limits.get('reset', 0)
                    
                    # Update our internal state
                    self.update_token_rate_limit_data(token, limit, remaining, reset_timestamp)
                    
                    # Format status
                    percentage = (remaining / limit * 100) if limit > 0 else 0
                    emoji = "🟢" if percentage > 50 else "🟡" if percentage > 20 else "🔴"
                    
                    # Add reset time if low
                    if remaining < 500 and reset_timestamp > current_time:
                        reset_dt = datetime.fromtimestamp(reset_timestamp)
                        reset_str = f" @{reset_dt.strftime('%H:%M')}"
                    else:
                        reset_str = ""
                    
                    # Mark current token
                    is_current = (token == original_token)
                    current_marker = "*" if is_current else " "
                    
                    # Mark token as exhausted if remaining is 0 (but not if it's -1, which means not checked yet)
                    if remaining == 0 and self.token_states[token]['remaining'] != -1:
                        # Debug: log what we're getting from GitHub
                        if self.verbose:
                            from datetime import datetime
                            print(f"    DEBUG: Token {i+1} exhausted. Reset timestamp from API: {reset_timestamp}")
                            print(f"    DEBUG: Current time: {current_time}")
                            print(f"    DEBUG: Reset time: {datetime.fromtimestamp(reset_timestamp)} (in {reset_timestamp - current_time:.0f}s)")
                        
                        # If we have a valid reset timestamp, use it; otherwise use a default 1 hour from now
                        if reset_timestamp > current_time:
                            self.mark_token_globally_exhausted(token, reset_timestamp)
                        else:
                            # No valid reset time or it's in the past, use the actual timestamp from GitHub
                            # GitHub rate limits reset on a rolling hour window, so use what they tell us
                            if reset_timestamp > 0:
                                self.mark_token_globally_exhausted(token, reset_timestamp)
                            else:
                                # Only fall back to 1 hour if we truly have no reset time
                                self.mark_token_globally_exhausted(token, current_time + 3600)
                    
                    statuses.append(f"{emoji} T{i+1}{current_marker}: {remaining}/{limit}{reset_str}")
                else:
                    # Error fetching rate limit - don't assume exhausted
                    error_msg = rate_limit_data.get('error', 'Unknown error')
                    if self.verbose:
                        print(f"  ⚠️ Error checking token {i+1}: {error_msg}")
                    # Show error status but don't mark as exhausted
                    statuses.append(f"❓ T{i+1}: Check failed")
                    
            except Exception as e:
                if self.verbose:
                    print(f"  ❌ Exception checking token {i+1}: {str(e)}")
                statuses.append(f"❓ T{i+1}: Error")
        
        # Restore original token
        github_client.current_token = original_token
        github_client._reinitialize_github_instance()
        
        # Print compact status
        print(f"💎 Tokens: {' | '.join(statuses)}")
        
        # If any are very low, add a note
        very_low = any("🔴" in s for s in statuses)
        if very_low:
            print("   (🔴 = <20% remaining, will auto-rotate when exhausted)") 