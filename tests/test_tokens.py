#!/usr/bin/env python3
"""Test script to verify GitHub tokens are working correctly"""

import asyncio
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gh_finder.api.token_manager import TokenManager
from gh_finder.api.client import GitHubClient

async def test_tokens():
    """Test token authentication and rate limit checking"""
    
    # Get tokens from environment
    tokens_str = os.getenv('GITHUB_TOKENS', '')
    if not tokens_str:
        print("❌ No tokens found in GITHUB_TOKENS environment variable")
        return
        
    tokens = [t.strip() for t in tokens_str.split(',') if t.strip()]
    print(f"✅ Found {len(tokens)} tokens to test\n")
    
    # Create token manager with verbose mode
    token_manager = TokenManager(tokens, verbose=True)
    
    # Create GitHub client with verbose mode
    github_client = GitHubClient(token_manager=token_manager, verbose=True)
    
    print("="*60)
    print("🧪 TESTING TOKEN AUTHENTICATION AND RATE LIMITS")
    print("="*60)
    
    # Test each token individually
    for i, token in enumerate(tokens):
        print(f"\n--- Testing Token {i+1} ---")
        github_client.current_token = token
        github_client._reinitialize_github_instance()
        
        # Try to get rate limit info
        rate_limit_data = await github_client._get_rate_limit_info()
        
        if 'error' in rate_limit_data:
            print(f"❌ Token {i+1} failed: {rate_limit_data['error']}")
        else:
            core = rate_limit_data.get('resources', {}).get('core', {})
            remaining = core.get('remaining', 0)
            limit = core.get('limit', 5000)
            print(f"✅ Token {i+1} is valid: {remaining}/{limit} API calls remaining")
    
    print("\n" + "="*60)
    print("🎯 TESTING COMPACT STATUS DISPLAY")
    print("="*60)
    
    # Test the compact status display
    await token_manager.print_compact_status(github_client)
    
    # Check global exhaustion status
    is_exhausted, earliest_reset = token_manager.get_global_exhaustion_status()
    
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    
    if is_exhausted:
        print("❌ All tokens are marked as exhausted")
        if earliest_reset:
            from datetime import datetime
            reset_dt = datetime.fromtimestamp(earliest_reset)
            print(f"⏰ Earliest reset: {reset_dt}")
    else:
        print("✅ Tokens are available for use")
        print("💡 The tool should work correctly now")
    
    # Cleanup
    await github_client.close_session()

if __name__ == "__main__":
    asyncio.run(test_tokens()) 