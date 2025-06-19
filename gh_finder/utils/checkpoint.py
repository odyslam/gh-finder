"""
Checkpoint functionality for saving and resuming state during GitHub profile analysis
"""

import os
import json
import time
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Union

class CheckpointManager:
    """Manages saving and loading checkpoint data during GitHub profile analysis"""
    
    def __init__(self, run_context=None):
        """Initialize the checkpoint manager
        
        Args:
            run_context: Optional run context for output directory
        """
        self.run_context = run_context
        
        # Use run context's checkpoint directory if available
        if self.run_context:
            if hasattr(self.run_context, 'checkpoint_dir'):
                self.run_checkpoints_dir = self.run_context.checkpoint_dir
            else:
                self.run_checkpoints_dir = os.path.join(self.run_context.run_dir, "checkpoints")
                os.makedirs(self.run_checkpoints_dir, exist_ok=True)
        
    def save_checkpoint(self, 
                      analyzed_users: Set[str], 
                      analyzed_repositories: Union[Set, List],
                      profiles: Dict[str, Any],
                      pr_merger_stats: Dict[str, int],
                      pr_merger_details: Dict[str, List],
                      contributor_stats: Dict[str, Dict[str, int]],
                      all_users: Set[str] = None,
                      remaining_users: Set[str] = None,
                      rate_limit_info: Dict = None,
                      repo_tiers: Dict[str, int] = None) -> Optional[str]:
        """Save a checkpoint file with the current state
        
        Args:
            analyzed_users: Set of analyzed users
            analyzed_repositories: Set of analyzed repositories
            profiles: Dictionary of profiles (username -> GitHubProfile)
            pr_merger_stats: Dictionary of PR merger stats (username -> count)
            pr_merger_details: Dictionary of PR merger details (username -> list of details)
            contributor_stats: Dictionary of contributor stats (username -> repo -> count)
            all_users: Optional set of all users to analyze
            remaining_users: Optional set of remaining users to analyze
            rate_limit_info: Optional rate limit information
            
        Returns:
            Optional[str]: Path to the checkpoint file or None on error
        """
        try:
            # Choose the checkpoint directory
            if self.run_context and hasattr(self, 'run_checkpoints_dir'):
                checkpoint_dir = self.run_checkpoints_dir
            else:
                # Create a default checkpoints directory in runs
                default_run_dir = os.path.join("./runs", "default")
                checkpoint_dir = os.path.join(default_run_dir, "checkpoints")
                os.makedirs(checkpoint_dir, exist_ok=True)
                
            # Create timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            checkpoint_file = os.path.join(checkpoint_dir, f"checkpoint_{timestamp}.json")
            
            # Ensure checkpoint directory exists
            os.makedirs(os.path.dirname(checkpoint_file), exist_ok=True)
            
            # Convert sets to lists for JSON serialization
            # Handle special types in analyzed_repositories
            serialized_repos = []
            for repo in analyzed_repositories:
                try:
                    # Handle different types of repository identifiers
                    if isinstance(repo, (tuple, list, frozenset, set)):
                        # Convert complex types to a string representation
                        serialized_repos.append(str(repo))
                    elif isinstance(repo, dict):
                        # For dictionaries, try to extract a name or convert to string
                        if "name" in repo:
                            serialized_repos.append(str(repo["name"]))
                        elif "full_name" in repo:
                            serialized_repos.append(str(repo["full_name"]))
                        else:
                            # Convert the dict to a simplified string representation
                            serialized_repos.append(str({k: str(v)[:50] for k, v in repo.items()}))
                    else:
                        # For simple types, convert to string
                        serialized_repos.append(str(repo))
                except Exception as e:
                    print(f"⚠️ Warning: Could not serialize repository: {e}")
                    # Skip problematic repositories
                    continue
            
            # Sanitize profiles for serialization
            sanitized_profiles = {}
            for username, profile in profiles.items():
                try:
                    # Skip invalid profiles
                    if not profile:
                        continue
                    
                    # Skip minimal profiles (likely failed fetches)
                    # Check if it's a GitHubProfile object with attributes
                    if hasattr(profile, 'created_at') and hasattr(profile, 'followers'):
                        # This is a GitHubProfile object
                        if (profile.created_at is None and 
                            profile.followers == 0 and 
                            profile.public_repos == 0 and
                            profile.bio is None and
                            profile.name is None and
                            profile.updated_at is None):
                            print(f"⚠️ Skipping minimal profile for {username} in checkpoint")
                            continue
                        
                    # Use to_dict method if available, otherwise use the profile object itself
                    if hasattr(profile, 'to_dict') and callable(profile.to_dict):
                        profile_dict = profile.to_dict()
                    else:
                        # If it's already a dict, use it directly
                        profile_dict = profile if isinstance(profile, dict) else {"username": str(profile)}
                        
                    # Validate the profile has a username
                    if not profile_dict.get("username"):
                        profile_dict["username"] = username
                        
                    sanitized_profiles[username] = profile_dict
                except Exception as e:
                    print(f"⚠️ Warning: Could not serialize profile for {username}: {e}")
                    # Create a minimal valid profile as fallback
                    sanitized_profiles[username] = {"username": username}
            
            # Sanitize PR merger stats (ensure all keys and values are valid)
            sanitized_pr_merger_stats = {}
            for username, count in pr_merger_stats.items():
                try:
                    if not username or not isinstance(username, str):
                        continue
                    sanitized_pr_merger_stats[username] = int(count) if isinstance(count, (int, float)) else 0
                except (ValueError, TypeError):
                    # Use 0 as fallback for invalid counts
                    sanitized_pr_merger_stats[username] = 0
                    
            # Sanitize PR merger details for serialization
            sanitized_pr_merger_details = {}
            for username, details in pr_merger_details.items():
                if not username or not isinstance(username, str) or not details:
                    continue
                    
                valid_details = []
                for detail in details:
                    try:
                        if isinstance(detail, (list, tuple)) and len(detail) >= 3:
                            # Ensure each component is a valid serializable type
                            repo = str(detail[0]) if detail[0] else ""
                            if not repo:
                                continue
                                
                            count = int(detail[1]) if isinstance(detail[1], (int, float)) else 0
                            tier = int(detail[2]) if isinstance(detail[2], (int, float)) else 99
                            
                            valid_details.append((repo, count, tier))
                    except Exception:
                        # Skip invalid details
                        continue
                        
                if valid_details:
                    sanitized_pr_merger_details[username] = valid_details
                    
            # Sanitize contributor stats for serialization
            sanitized_contributor_stats = {}
            for username, repo_stats in contributor_stats.items():
                if not username or not isinstance(username, str) or not repo_stats:
                    continue
                    
                valid_stats = {}
                for repo, count in repo_stats.items():
                    if not repo or not isinstance(repo, str):
                        continue
                        
                    try:
                        valid_stats[repo] = int(count) if isinstance(count, (int, float)) else 0
                    except (ValueError, TypeError):
                        # Use 0 as fallback for invalid counts
                        valid_stats[repo] = 0
                        
                if valid_stats:
                    sanitized_contributor_stats[username] = valid_stats
            
            # Validate users sets
            sanitized_all_users = []
            if all_users:
                for user in all_users:
                    if user and isinstance(user, str):
                        sanitized_all_users.append(user)
                    
            sanitized_remaining_users = []
            if remaining_users:
                for user in remaining_users:
                    if user and isinstance(user, str):
                        sanitized_remaining_users.append(user)
                        
            # Validate analyzed users set
            sanitized_analyzed_users = []
            for user in analyzed_users:
                if user and isinstance(user, str):
                    sanitized_analyzed_users.append(user)
            
            # Create the final checkpoint data structure
            checkpoint_data = {
                "timestamp": timestamp,
                "analyzed_users": sanitized_analyzed_users,
                "analyzed_repositories": serialized_repos,
                "profiles": sanitized_profiles,
                "pr_merger_stats": sanitized_pr_merger_stats,
                "pr_merger_details": sanitized_pr_merger_details,
                "contributor_stats": sanitized_contributor_stats,
                "all_users": sanitized_all_users,
                "remaining_users": sanitized_remaining_users,
                "rate_limit_info": rate_limit_info if isinstance(rate_limit_info, dict) else {},
                "repo_tiers": repo_tiers if isinstance(repo_tiers, dict) else {}
            }
            
            # Save checkpoint data to file
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2)
                
            print(f"✅ Created checkpoint: {checkpoint_file}")
            return str(checkpoint_file)
        except Exception as e:
            print(f"❌ Error creating checkpoint: {str(e)}")
            traceback.print_exc()
            return None
            
    def load_checkpoint(self, checkpoint_file: str) -> Optional[Dict]:
        """Load a checkpoint file
        
        Args:
            checkpoint_file: Path to the checkpoint file
            
        Returns:
            Dict: Checkpoint data or None if loading failed
        """
        # First check if the file exists
        if not os.path.isfile(checkpoint_file):
            print(f"❌ Checkpoint file not found: {checkpoint_file}")
            # Try to find the file in common locations
            default_run_dir = os.path.join("./runs", "default", "checkpoints")
            if os.path.isfile(os.path.join(default_run_dir, os.path.basename(checkpoint_file))):
                checkpoint_file = os.path.join(default_run_dir, os.path.basename(checkpoint_file))
                print(f"✅ Found checkpoint file in default run directory: {checkpoint_file}")
            else:
                print(f"❌ Could not find checkpoint file in common locations, tried {checkpoint_file}")
                return None
        
        try:
            with open(checkpoint_file, "r") as f:
                checkpoint_data = json.load(f)
                
            # Log the checkpoint structure for debugging
            print(f"📝 Loaded checkpoint from {checkpoint_file}")
            
            # Add explicit debug info about what's in the checkpoint
            profile_count = len(checkpoint_data.get("profiles", {}))
            analyzed_users_count = len(checkpoint_data.get("analyzed_users", []))
            analyzed_repos_count = len(checkpoint_data.get("analyzed_repositories", []))
            print(f"📊 Checkpoint contains: {profile_count} profiles, {analyzed_users_count} users, {analyzed_repos_count} repositories")
            
            # Validate the checkpoint data more robustly - don't reject legitimate empty data
            if "analyzed_users" not in checkpoint_data:
                print("⚠️ Warning: 'analyzed_users' field missing from checkpoint - initializing as empty list")
                checkpoint_data["analyzed_users"] = []
                
            if "analyzed_repositories" not in checkpoint_data:
                print("⚠️ Warning: 'analyzed_repositories' field missing from checkpoint - initializing as empty list")
                checkpoint_data["analyzed_repositories"] = []
                
            if "profiles" not in checkpoint_data:
                print("⚠️ Warning: 'profiles' field missing from checkpoint - initializing as empty dict")
                checkpoint_data["profiles"] = {}
                
            if "pr_merger_stats" not in checkpoint_data:
                print("⚠️ Warning: 'pr_merger_stats' field missing from checkpoint - initializing as empty dict")
                checkpoint_data["pr_merger_stats"] = {}
                
            if "pr_merger_details" not in checkpoint_data:
                print("⚠️ Warning: 'pr_merger_details' field missing from checkpoint - initializing as empty dict")
                checkpoint_data["pr_merger_details"] = {}
                
            if "contributor_stats" not in checkpoint_data:
                print("⚠️ Warning: 'contributor_stats' field missing from checkpoint - initializing as empty dict")
                checkpoint_data["contributor_stats"] = {}
                
            # Ensure all_users and remaining_users exist
            if "all_users" not in checkpoint_data:
                checkpoint_data["all_users"] = []
                
            if "remaining_users" not in checkpoint_data:
                checkpoint_data["remaining_users"] = []
            
            return checkpoint_data
        except (IOError, json.JSONDecodeError) as e:
            print(f"❌ Error loading checkpoint: {str(e)}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error loading checkpoint: {str(e)}")
            traceback.print_exc()
            return None
            
    def list_checkpoints(self) -> List[str]:
        """List all available checkpoint files
        
        Returns:
            List[str]: List of checkpoint file paths
        """
        checkpoints = []
        
        # First, check run-specific checkpoints if we have a run context
        if self.run_context and hasattr(self, 'run_checkpoints_dir'):
            run_checkpoints = sorted(
                Path(self.run_checkpoints_dir).glob("checkpoint_*.json"), 
                reverse=True
            )
            checkpoints.extend([str(f) for f in run_checkpoints])
        
        # Also check the default run directory
        default_run_dir = Path("./runs/default/checkpoints")
        if default_run_dir.exists():
            default_checkpoints = sorted(
                default_run_dir.glob("checkpoint_*.json"),
                reverse=True
            )
            # Add these, but avoid duplicates
            for cp in default_checkpoints:
                cp_str = str(cp)
                if cp_str not in checkpoints:
                    checkpoints.append(cp_str)
        
        return checkpoints
    
    @staticmethod
    def list_all_checkpoints() -> Dict[str, List[str]]:
        """List all checkpoints organized by run
        
        Returns:
            Dict mapping run names to lists of checkpoint files
        """
        all_checkpoints = {}
        
        # Check all run directories
        runs_dir = Path("./runs")
        if runs_dir.exists():
            for run_dir in sorted(runs_dir.iterdir(), reverse=True):
                if run_dir.is_dir():
                    run_name = run_dir.name
                    checkpoint_dir = run_dir / "checkpoints"
                    if checkpoint_dir.exists():
                        checkpoints = sorted(
                            checkpoint_dir.glob("checkpoint_*.json"),
                            reverse=True
                        )
                        if checkpoints:
                            all_checkpoints[run_name] = [cp.name for cp in checkpoints]
        
        # Also check default run directory
        default_dir = Path("./runs/default/checkpoints")
        if default_dir.exists():
            default_checkpoints = sorted(
                default_dir.glob("checkpoint_*.json"),
                reverse=True
            )
            if default_checkpoints:
                all_checkpoints["default"] = [cp.name for cp in default_checkpoints]
        
        return all_checkpoints
        
    def get_latest_checkpoint(self) -> Optional[str]:
        """Get the most recent checkpoint file
        
        Returns:
            Optional[str]: Path to latest checkpoint file or None if no checkpoints exist
        """
        checkpoint_files = self.list_checkpoints()
        if not checkpoint_files:
            return None
            
        return checkpoint_files[0]
    
    @staticmethod
    def get_latest_checkpoint_for_run(run_name: str) -> Optional[str]:
        """Get the latest checkpoint for a specific run
        
        Args:
            run_name: Name of the run (timestamp)
            
        Returns:
            Optional[str]: Path to latest checkpoint or None
        """
        run_dir = Path(f"./runs/{run_name}")
        if not run_dir.exists():
            return None
            
        checkpoint_dir = run_dir / "checkpoints"
        if not checkpoint_dir.exists():
            return None
            
        checkpoints = sorted(
            checkpoint_dir.glob("checkpoint_*.json"),
            reverse=True
        )
        
        if not checkpoints:
            return None
            
        return str(checkpoints[0])
        
    def get_checkpoint_path(self, checkpoint_name: str) -> str:
        """Get the full path to a checkpoint file from its name
        
        Args:
            checkpoint_name: Name or basename of the checkpoint file, or run name
            
        Returns:
            str: Full path to the checkpoint file
        """
        # If the full path is provided, return it
        if os.path.isfile(checkpoint_name):
            return checkpoint_name
        
        # Check if it's a run name (format: YYYYMMDD_HHMMSS)
        if len(checkpoint_name) == 15 and checkpoint_name[8] == '_':
            # Try to find the latest checkpoint in this run
            latest = self.get_latest_checkpoint_for_run(checkpoint_name)
            if latest:
                return latest
            # If not found, continue with other checks
            
        # Check different possible locations for the checkpoint file
        # 1. Current directory
        if os.path.isfile(os.path.join(".", checkpoint_name)):
            return os.path.join(".", checkpoint_name)
            
        # 2. Look in checkpoints directory of run context if available
        if self.run_context:
            # Try the checkpoint_dir attribute if available
            if hasattr(self.run_context, 'checkpoint_dir'):
                checkpoint_dir = self.run_context.checkpoint_dir
                if os.path.isfile(os.path.join(checkpoint_dir, checkpoint_name)):
                    return os.path.join(checkpoint_dir, checkpoint_name)
            
            # Fallback to run_dir/checkpoints
            checkpoint_dir = os.path.join(self.run_context.run_dir, "checkpoints")
            if os.path.isfile(os.path.join(checkpoint_dir, checkpoint_name)):
                return os.path.join(checkpoint_dir, checkpoint_name)
                
        # 3. Check in default run directory
        default_checkpoint_dir = "./runs/default/checkpoints"
        if os.path.isfile(os.path.join(default_checkpoint_dir, checkpoint_name)):
            return os.path.join(default_checkpoint_dir, checkpoint_name)
        
        # 4. Try to find in any run directory
        runs_dir = Path("./runs")
        if runs_dir.exists():
            for run_dir in runs_dir.iterdir():
                if run_dir.is_dir():
                    checkpoint_path = run_dir / "checkpoints" / checkpoint_name
                    if checkpoint_path.exists():
                        return str(checkpoint_path)
            
        # If we still haven't found it, return the name as is and let the caller handle errors
        return checkpoint_name

    @staticmethod
    def load(path: str, verbose: bool = False) -> Dict[str, Any]:
        """Load checkpoint data from a file
        
        Args:
            path: Path to the checkpoint file
            verbose: Whether to print verbose output
            
        Returns:
            Dict[str, Any]: Checkpoint data
        """
        if not os.path.exists(path):
            if verbose:
                print(f"Checkpoint file '{path}' does not exist")
            return {}
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                
            if not isinstance(data, dict):
                print(f"WARNING: Invalid checkpoint data format in '{path}'. Expected a dictionary.")
                return {}
                
            # Validate and initialize key fields if missing
            # These are the fields that have been causing issues
            for profile_data in data.get('analyzed_profiles', {}).values():
                if isinstance(profile_data, dict):
                    # Ensure repos field exists and is a list
                    if 'repos' not in profile_data or not isinstance(profile_data['repos'], list):
                        profile_data['repos'] = []
                        
                    # Ensure merged_at field exists and is a dict
                    if 'merged_at' not in profile_data or not isinstance(profile_data['merged_at'], dict):
                        profile_data['merged_at'] = {}
                        
                    # Ensure repos_appeared_in field exists and is a list
                    if 'repos_appeared_in' not in profile_data or not isinstance(profile_data['repos_appeared_in'], list):
                        profile_data['repos_appeared_in'] = []
                        
                    # Ensure all collection fields are initialized
                    for field in ['top_repos', 'languages', 'languages_detailed', 'prs_merged_details', 'cross_repo_details']:
                        if field not in profile_data or profile_data[field] is None:
                            profile_data[field] = []
                
            if verbose:
                print(f"Loaded checkpoint from '{path}'")
            return data
            
        except json.JSONDecodeError as e:
            print(f"WARNING: Invalid JSON in checkpoint file '{path}': {str(e)}")
            return {}
            
        except Exception as e:
            print(f"ERROR: Failed to load checkpoint from '{path}': {str(e)}")
            return {} 