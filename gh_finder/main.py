"""
Main entry point for the GitHub Profile Finder
"""

import argparse
import asyncio
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from .api.token_manager import TokenManager
from .core.finder import GitHubProfileFinder
from .utils.config import load_config_file, create_sample_config, load_env_vars, load_tokens_from_file
from .utils.run_context import RunContext, current_run
from .utils.checkpoint import CheckpointManager
from .api.client import GitHubRateLimitError, GitHubClient

# Global finder instance for signal handling
_finder = None
# Global event loop reference for signal handling
_loop = None
# Flag to indicate if we've been interrupted
_interrupted = False

async def cleanup_resources():
    """Clean up any open resources before exiting"""
    global _finder
    if _finder and hasattr(_finder, 'github'):
        await _finder.close()

def signal_handler(sig, frame):
    """Handle interrupt signals (CTRL+C)"""
    global _interrupted
    
    # Only handle the first interrupt
    if _interrupted:
        print("\n⚠️ Second interrupt detected. Forcing exit...")
        os._exit(1)
    
    _interrupted = True
    print("\n\n⚠️ Interrupt received, creating checkpoint before exiting...")
    
    if _finder is not None:
        # Create a checkpoint with the current state
        try:
            checkpoint_file = _finder._create_checkpoint(force=True)
            if checkpoint_file:
                print(f"✅ Checkpoint created: {checkpoint_file}")
                print(f"🔄 Resume with: uv run gh_finder.py --resume {os.path.basename(checkpoint_file)} --config repos_config.toml")
        except Exception as e:
            print(f"❌ Error creating checkpoint: {str(e)}")
    
    # Set alarm to force exit after timeout
    signal.signal(signal.SIGALRM, lambda sig, frame: os._exit(1))
    signal.alarm(5)  # Force exit after 5 seconds
    
    # Exit after checkpoint is created
    print("👋 Exiting gracefully...")
    sys.exit(130)  # Standard exit code for SIGINT

async def run_finder(args, token_manager=None):
    """Run the GitHub Profile Finder with the provided arguments"""
    global current_run
    global _finder
    global _loop
    global _interrupted
    
    # Store the current event loop for signal handling
    _loop = asyncio.get_event_loop()
    
    # Create run context for logging
    current_run = RunContext()
    
    # Load tokens
    tokens = []
    
    # Load tokens from command line
    if args.token:
        tokens.append(args.token)
    
    # Load tokens from environment variables
    env_tokens = load_env_vars()
    if env_tokens:
        tokens.extend(env_tokens)
    
    # Load tokens from file
    if args.tokens_file:
        file_tokens = load_tokens_from_file(args.tokens_file)
        if file_tokens:
            tokens.extend(file_tokens)
    
    if not tokens:
        print("❌ No GitHub API tokens provided. Please provide at least one token.")
        print("   Use --token, set GITHUB_TOKEN environment variable, or use --tokens-file")
        sys.exit(1)
    
    # Setup GitHub token manager
    if token_manager is None:
        token_manager = TokenManager(tokens)
    
    # Create checkpoint manager
    checkpoint_manager = CheckpointManager(current_run)
    
    # Process command line arguments
    if args.list_checkpoints:
        # List available checkpoints organized by run
        all_checkpoints = CheckpointManager.list_all_checkpoints()
        
        if all_checkpoints:
            print("📋 Available checkpoints:")
            print("")
            
            # Show run-specific checkpoints first
            for run_name, checkpoints in sorted(all_checkpoints.items(), reverse=True):
                if run_name == "default":
                    continue  # Show these last
                    
                print(f"📁 Run: {run_name}")
                # Try to get run info if available
                run_log = Path(f"./runs/{run_name}/output.log")
                if run_log.exists():
                    # Read first few lines to get context
                    with open(run_log, 'r') as f:
                        lines = f.readlines()[:5]
                        for line in lines:
                            if "Loaded configuration from" in line:
                                print(f"   Config: {line.strip()}")
                                break
                
                for checkpoint in checkpoints:
                    print(f"   - {checkpoint}")
                print("")
            
            # Show default checkpoints if any
            if "default" in all_checkpoints:
                print(f"📁 Default checkpoints:")
                for checkpoint in all_checkpoints["default"]:
                    print(f"   - {checkpoint}")
                print("")
            
            print("💡 Resume from a run: --resume RUN_NAME (e.g., --resume 20250115_143022)")
            print("💡 Resume from latest: --resume latest")
            print("💡 Resume specific checkpoint: --resume checkpoint_20250115_143022.json")
        else:
            print("❌ No checkpoints found")
        
        sys.exit(0)
    
    # Check tokens status
    if args.check_tokens:
        print("🔍 Checking GitHub API tokens status...")
        github_client = GitHubClient(token_manager=token_manager, verbose=args.verbose)
        
        # Check all tokens
        try:
            status_report = await token_manager.check_all_tokens_status(github_client)
            
            if not status_report['any_available']:
                print("\n⚠️ No tokens have remaining API calls!")
                print("💡 Wait for rate limits to reset or add more tokens")
                sys.exit(1)
            else:
                print("\n✅ Some tokens are available for use")
                sys.exit(0)
                
        except Exception as e:
            print(f"❌ Error checking tokens: {str(e)}")
            sys.exit(1)
    
    # Save a reference to any finder we create, for proper cleanup
    finder_for_cleanup = None
    
    try:
        # If resuming, load checkpoint
        checkpoint_file = None
        if args.resume:
            print("🔄 Resuming from checkpoint")
            
            if args.resume == 'latest':
                checkpoint_file = checkpoint_manager.get_latest_checkpoint()
                if not checkpoint_file:
                    print("❌ No checkpoints found")
                    sys.exit(1)
                    
                print(f"📂 Using latest checkpoint: {checkpoint_file}")
            else:
                # Check if it's a run name
                if len(args.resume) == 15 and args.resume[8] == '_':
                    # It looks like a run name
                    run_dir = Path(f"./runs/{args.resume}")
                    if run_dir.exists():
                        print(f"📁 Found run: {args.resume}")
                        checkpoint_file = CheckpointManager.get_latest_checkpoint_for_run(args.resume)
                        if checkpoint_file:
                            print(f"📂 Using latest checkpoint from run: {Path(checkpoint_file).name}")
                        else:
                            print(f"❌ No checkpoints found in run {args.resume}")
                            sys.exit(1)
                    else:
                        print(f"❌ Run not found: {args.resume}")
                        print(f"💡 Available runs:")
                        runs_dir = Path("./runs")
                        if runs_dir.exists():
                            for run in sorted(runs_dir.iterdir(), reverse=True)[:10]:
                                if run.is_dir():
                                    print(f"   - {run.name}")
                        sys.exit(1)
                else:
                    # Use provided checkpoint file
                    checkpoint_file = checkpoint_manager.get_checkpoint_path(args.resume)
                    if not os.path.exists(checkpoint_file):
                        print(f"❌ Checkpoint file not found: {args.resume}")
                        # Provide helpful suggestions
                        print("\n💡 Try one of these options:")
                        print("   --resume latest                    # Resume from most recent checkpoint")
                        print("   --resume 20250115_143022           # Resume from a specific run")
                        print("   --resume checkpoint_20250115.json  # Resume from specific checkpoint file")
                        print("\nUse --list-checkpoints to see all available checkpoints")
                        sys.exit(1)
                        
                    print(f"📂 Using checkpoint: {checkpoint_file}")
            
            # Check rate limits before resuming
            finder = GitHubProfileFinder(
                token_manager=token_manager,
                run_context=current_run,
                verbose=args.verbose, 
                analyze_prs=args.analyze_prs,
                force_reanalyze=args.force_reanalyze,
                checkpoint_file=checkpoint_file
            )
            
            # Keep reference for cleanup
            finder_for_cleanup = finder
            
            try:
                # Check rate limits before resuming
                rate_limit_info = await finder.get_rate_limit_info()
                if 'error' in rate_limit_info:
                    print(f"⚠️ Warning: Could not check rate limit: {rate_limit_info.get('error')}")
                elif 'resources' in rate_limit_info:
                    core_limits = rate_limit_info.get('resources', {}).get('core', {})
                    remaining = core_limits.get('remaining', 0)
                    if remaining < 100:  # Low threshold
                        print(f"⚠️ Warning: Low rate limit remaining: {remaining}")
                        print("Consider waiting for rate limit to reset before resuming.")
            except Exception as e:
                print(f"⚠️ Warning: Could not check rate limit: {str(e)}")
                # Continue anyway - rate limits will be handled by the client during execution
        
        # Load config file
        if args.config:
            config_path = args.config
            
            if not os.path.exists(config_path):
                print(f"❌ Config file not found: {config_path}")
                print("Creating a sample config file...")
                create_sample_config(config_path)
                print(f"✅ Sample config file created at {config_path}")
                print("Please edit this file and run the program again.")
                sys.exit(0)
                
            config = load_config_file(config_path)
            if not config:
                print(f"❌ Error loading config file: {config_path}")
                sys.exit(1)
                
            # Use configuration
            tiered_repositories = config.get('repositories', [])
            
            if not tiered_repositories:
                print("❌ No repositories defined in config file")
                sys.exit(1)
            
            # Flatten tiered repositories into a list of (repo, tier) tuples
            repositories = []
            for tier_index, tier_repos in enumerate(tiered_repositories):
                for repo_entry in tier_repos:
                    if isinstance(repo_entry, dict) and 'name' in repo_entry:
                        repositories.append((repo_entry['name'], tier_index, repo_entry.get('label', '')))
                    elif isinstance(repo_entry, str):
                        repositories.append((repo_entry, tier_index, ''))
            
            print(f"📋 Loaded configuration from {config_path}")
            print(f"🔍 Will analyze {len(repositories)} repositories across {len(tiered_repositories)} tiers")
            
            # Create or reuse GitHub profile finder
            if 'finder' in locals() and args.resume:
                # Update the existing finder with configuration
                finder.config = config
                # Keep using the existing finder that has the loaded checkpoint state
                print("🔄 Using finder with loaded checkpoint state")
            else:
                # Create a new finder instance
                finder = GitHubProfileFinder(
                    token_manager=token_manager,
                    run_context=current_run,
                    verbose=args.verbose, 
                    analyze_prs=args.analyze_prs,
                    force_reanalyze=args.force_reanalyze,
                    config=config,
                    checkpoint_file=checkpoint_file if args.resume else None  # Explicitly pass checkpoint_file
                )
            
            # Keep reference for cleanup
            finder_for_cleanup = finder
            
            # Store the finder in the global variable for signal handling
            _finder = finder
            
            # Register signal handler for CTRL+C
            signal.signal(signal.SIGINT, signal_handler)
            
            try:
                # Check if we've been interrupted before even starting
                if _interrupted:
                    print("🛑 Detected interrupt before analysis started")
                    return
                
                # Start analysis - pass interrupted flag check function
                async def check_interrupted():
                    return _interrupted
                
                profiles = await finder.analyze_repositories(
                    repositories, 
                    args.limit, 
                    checkpoint_file=checkpoint_file,
                    force_reanalyze=args.force_reanalyze,
                    interrupt_check=check_interrupted
                )
                
                # Check if we actually did any work (profiles might be empty if tokens exhausted)
                # The analyze_repositories method returns existing profiles without work if tokens exhausted
                if not profiles and finder.token_manager:
                    # Check if it was due to token exhaustion
                    is_exhausted, _ = finder.token_manager.get_global_exhaustion_status()
                    if is_exhausted:
                        print("\n✅ Exited cleanly due to exhausted tokens.")
                        print("💡 No work was performed. Resume when tokens are available.")
                        return
                
                # Print results only if not interrupted
                if not _interrupted:
                    finder.print_profile_summary()
                    
                    # Generate LLM analysis if requested
                    if args.llm_output:
                        print("\n" + "="*80)
                        print("📊 Generating LLM analysis output...")
                        if args.llm_output == "console":
                            finder.print_llm_analysis()
                        else:
                            # Use provided filename or generate one
                            llm_output_file = args.llm_output
                            if llm_output_file == "auto":
                                llm_output_file = f"llm_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                            finder.print_llm_analysis(llm_output_file)
            except GitHubRateLimitError as e:
                # Handle rate limit exhaustion gracefully
                if e.global_exhaustion:
                    print("\n" + "="*60)
                    print("🛑 ALL GITHUB API TOKENS ARE EXHAUSTED")
                    print("="*60)
                    
                    if e.earliest_reset_timestamp:
                        from datetime import datetime
                        import time
                        reset_dt = datetime.fromtimestamp(e.earliest_reset_timestamp)
                        reset_str = reset_dt.strftime('%Y-%m-%d %H:%M:%S')
                        time_until_reset = e.earliest_reset_timestamp - time.time()
                        
                        if time_until_reset < 3600:
                            time_until_str = f"{int(time_until_reset / 60)} minutes"
                        else:
                            time_until_str = f"{int(time_until_reset / 3600)} hours {int((time_until_reset % 3600) / 60)} minutes"
                        
                        print(f"\n⏰ Tokens will reset at: {reset_str}")
                        print(f"⏳ Time to wait: {time_until_str}")
                    else:
                        print("\n⚠️ Unable to determine when tokens will reset")
                        
                    print(f"\n💡 Your progress has been saved. Resume with:")
                    print(f"   ./run.py --resume latest --config {args.config}")
                    print("\n✅ Analysis stopped gracefully due to rate limits")
                else:
                    # Regular rate limit error
                    print(f"\n❌ Rate limit error: {str(e)}")
                    print(f"💡 Try adding more tokens or resuming later")
            finally:
                # Clean up resources before exiting
                await cleanup_resources()
        else:
            print("❌ No config file specified. Use --config option.")
            sys.exit(1)
    except SystemExit:
        # Ensure we clean up resources even on sys.exit() calls
        if finder_for_cleanup:
            try:
                await finder_for_cleanup.close()
            except Exception as e:
                print(f"⚠️ Warning: Error during exit cleanup: {e}")
        raise
    finally:
        # Ensure all resources are properly cleaned up
        if finder_for_cleanup:
            try:
                await finder_for_cleanup.close()
            except Exception as e:
                print(f"⚠️ Warning: Error during final cleanup: {e}")

def main(token_manager=None, verbose=False):
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Find promising GitHub developers from repository activity")
    parser.add_argument("--config", help="Path to TOML configuration file")
    parser.add_argument("--token", help="GitHub API token")
    parser.add_argument("--tokens-file", help="Path to file containing GitHub API tokens (one per line)")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of users to analyze (default: no limit)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--analyze-prs", action="store_true", help="Analyze PRs for contributors (API intensive)")
    parser.add_argument("--resume", help="Resume from checkpoint file (use 'latest' for most recent)")
    parser.add_argument("--list-checkpoints", action="store_true", help="List available checkpoints")
    parser.add_argument("--force-reanalyze", action="store_true", help="Force re-analysis of repositories even if previously analyzed")
    parser.add_argument("--llm-output", help="Generate LLM-friendly analysis output (use 'console' for stdout, 'auto' for timestamped file, or specify filename)")
    parser.add_argument("--check-tokens", action="store_true", help="Check all GitHub API tokens status")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Use provided verbose setting if specified
    if verbose:
        args.verbose = verbose
    
    # Setup debug mode if needed
    if args.verbose and os.environ.get('DEBUG_SESSIONS'):
        _setup_debug_logging()
    
    try:
        # Run the finder with appropriate arguments
        asyncio.run(run_finder(args, token_manager=token_manager))
        return 0  # Success
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        # Ensure cleanup runs
        asyncio.run(cleanup_resources())
        return 130  # Standard exit code for SIGINT
    except SystemExit as e:
        # System exit - allow normal exit
        return e.code
    except Exception as e:
        print(f"❌ Unhandled error: {str(e)}")
        import traceback
        traceback.print_exc()
        # Ensure cleanup runs
        asyncio.run(cleanup_resources())
        return 1  # Error

def _setup_debug_logging():
    """Setup debug logging for aiohttp sessions"""
    try:
        import aiohttp
        print("🐛 Debug mode: Adding logging for aiohttp sessions")
        
        # Wrap session initialization
        original_init = aiohttp.ClientSession.__init__
        def debug_init(self, *args, **kwargs):
            print(f"Creating aiohttp ClientSession {id(self)}")
            original_init(self, *args, **kwargs)
        aiohttp.ClientSession.__init__ = debug_init
        
        # Wrap session close
        original_close = aiohttp.ClientSession.close
        async def debug_close(self):
            print(f"Closing aiohttp ClientSession {id(self)}")
            return await original_close(self)
        aiohttp.ClientSession.close = debug_close
    except ImportError:
        print("⚠️ Could not setup debug logging: aiohttp not available")
    except Exception as e:
        print(f"⚠️ Error setting up debug logging: {e}")

if __name__ == "__main__":
    main() 