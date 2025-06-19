"""
Command-line interface for GitHub Profile Finder
"""

import sys
import argparse
import os

from .main import main as finder_main
from .api.token_manager import TokenManager
from .api.client import GitHubClient

def main():
    """CLI entry point that forwards to the actual main function"""
    # Set up token manager
    tokens = []
    
    # Read tokens from file or environment variables
    if args.token_file:
        token_file = args.token_file
        try:
            with open(token_file, 'r') as f:
                token_lines = f.readlines()
                for line in token_lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        tokens.append(line)
                        
            if not tokens:
                print(f"❌ No valid tokens found in file: {token_file}")
                sys.exit(1)
                
            print(f"✅ Loaded {len(tokens)} tokens from file")
        except Exception as e:
            print(f"❌ Error loading tokens from file {token_file}: {str(e)}")
            sys.exit(1)
    elif args.token:
        # Single token provided via CLI
        tokens.append(args.token)
    elif 'GITHUB_TOKEN' in os.environ:
        # Try to get token from environment variable
        tokens.append(os.environ.get('GITHUB_TOKEN'))
    else:
        print("❌ No GitHub token provided. Use --token, --token-file, or set GITHUB_TOKEN environment variable.")
        parser.print_help()
        sys.exit(1)
        
    # Initialize token manager with proper error handling
    token_manager = TokenManager(tokens, verbose=args.verbose)
    if not token_manager.tokens:
        print("❌ No valid GitHub tokens available.")
        sys.exit(1)
    elif args.verbose:
        print(f"✅ Using {len(token_manager.tokens)} GitHub API tokens")
    
    # Initialize GitHub client
    github_client = GitHubClient(token_manager, verbose=args.verbose)
    
    # Call the main finder function with our initialized components
    finder_main(
        token_manager=token_manager,
        github_client=github_client,
        verbose=args.verbose
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub Profile Finder CLI")
    parser.add_argument("--token-file", help="Path to a file containing GitHub tokens")
    parser.add_argument("--token", help="Single GitHub token")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()
    main() 