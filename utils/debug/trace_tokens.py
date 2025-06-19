#\!/usr/bin/env python3
"""
Debug script to trace token loading and handling through the application.
This script should show how many tokens are recognized by each component.
"""

import sys
import os
import dotenv
import argparse

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Load environment variables from .env file
dotenv.load_dotenv()

from gh_finder.utils.config import load_env_vars
from gh_finder.api.token_manager import TokenManager
from gh_finder.main import run_finder

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Debug token loading")
    parser.add_argument("--config", default="repos_config.toml", help="Config file")
    parser.add_argument("--resume", help="Resume from checkpoint")
    parser.add_argument("--token", help="GitHub token")
    parser.add_argument("--tokens-file", help="File with GitHub tokens")
    parser.add_argument("--analyze-prs", action="store_true", help="Analyze PRs")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--check-tokens", action="store_true", help="Check tokens")
    parser.add_argument("--list-checkpoints", action="store_true", help="List checkpoints")
    parser.add_argument("--limit", type=int, help="Limit users")
    parser.add_argument("--llm-output", help="LLM output")
    parser.add_argument("--force-reanalyze", action="store_true", help="Force reanalysis")
    args = parser.parse_args()

    # Load tokens
    print("=== Start token loading ===")
    tokens = load_env_vars()
    print(f"Load_env_vars returned {len(tokens)} tokens")

    # Create TokenManager
    tm = TokenManager(tokens, verbose=True)
    print(f"TokenManager initialized with {tm.get_token_count()} tokens")

    # Inspect token queue
    print("\nToken queue:")
    for i, token in enumerate(list(tm.tokens_queue)):
        print(f"  {i+1}: {token[:8]}...{token[-4:]}")

    # Pass TokenManager to run_finder
    import asyncio
    print("\n=== Starting run_finder with our TokenManager ===")

    # Intercept GitHubClient initialization to debug token handling
    from gh_finder.api.client import GitHubClient
    original_init = GitHubClient.__init__

    def debug_init(self, token=None, verbose=False, token_manager=None, per_page=100):
        print("\n=== GitHubClient.__init__ called ===")
        print(f"token: {token[:8] if token else 'None'}")
        print(f"token_manager has {token_manager.get_token_count() if token_manager else 0} tokens")
        
        if token_manager:
            for i, t in enumerate(list(token_manager.tokens_queue)):
                print(f"  {i+1}: {t[:8]}...{t[-4:]}")
        
        # Call original with same args
        result = original_init(self, token=token, verbose=verbose, token_manager=token_manager, per_page=per_page)
        
        print(f"After init, current_token: {self.current_token[:8] if self.current_token else 'None'}")
        return result

    GitHubClient.__init__ = debug_init

    try:
        asyncio.run(run_finder(args, token_manager=tm))
    except Exception as e:
        print(f"Error in run_finder: {e}")
    finally:
        # Restore original init
        GitHubClient.__init__ = original_init

if __name__ == "__main__":
    main()
