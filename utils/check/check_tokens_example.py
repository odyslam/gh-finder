#!/usr/bin/env python3
"""
Example script to check GitHub API tokens status
"""

import sys
import os
import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()

# Add the project root to the path so we can import gh_finder
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gh_finder.main import main

if __name__ == "__main__":
    # Add --check-tokens to sys.argv
    sys.argv.extend(["--check-tokens", "--verbose"])
    
    print("🔍 GitHub Token Status Checker")
    print("="*60)
    print("\nThis script will check all your GitHub API tokens and show:")
    print("- Remaining API calls for each token")
    print("- When rate limits will reset")
    print("- Whether you can continue analysis")
    print("\n" + "="*60 + "\n")
    
    # Run the main function with check-tokens flag
    exit_code = main()
    
    if exit_code == 0:
        print("\n✅ You're good to go! Some tokens have API calls remaining.")
    else:
        print("\n⚠️ All tokens are exhausted. Please wait for rate limits to reset.")
    
    sys.exit(exit_code) 