"""
Helper functions for GitHub Profile Finder tests
"""

import os
import sys
import asyncio
from typing import List, Dict, Any, Optional

def get_test_tokens() -> List[str]:
    """Get GitHub tokens from environment variables."""
    tokens = []
    
    # Check for individual token env vars
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN_1")
    if token:
        tokens.append(token)
    
    # Check for GITHUB_TOKENS (plural) with comma-separated tokens
    tokens_str = os.getenv("GITHUB_TOKENS")
    if tokens_str:
        tokens.extend([t.strip() for t in tokens_str.split(",") if t.strip()])
    
    # Remove duplicates while preserving order
    unique_tokens = []
    for token in tokens:
        if token not in unique_tokens:
            unique_tokens.append(token)
    
    return unique_tokens

def print_test_header(title: str):
    """Print a test header with consistent formatting."""
    print(f"\n🧪 {title}")
    print("=" * 80)

def print_test_section(title: str):
    """Print a test section with consistent formatting."""
    print(f"\n📋 {title}")
    print("-" * 60)

def print_test_result(title: str, success: bool):
    """Print a test result with consistent formatting."""
    if success:
        print(f"✅ {title}")
    else:
        print(f"❌ {title}")

async def check_rate_limit(client) -> Dict[str, Any]:
    """Check rate limit and return info."""
    print("\n📊 Checking rate limit...")
    rate_info = await client._get_rate_limit_info()
    if 'error' not in rate_info:
        core = rate_info.get('resources', {}).get('core', {})
        remaining = core.get('remaining', 0)
        limit = core.get('limit', 5000)
        print(f"✅ Rate limit: {remaining}/{limit} requests remaining")
        
        if remaining < 100:
            print("⚠️ Warning: Low API rate limit remaining!")
    else:
        print(f"❌ Error checking rate limit: {rate_info.get('error')}")
    
    return rate_info

# Test repositories that are stable and good for testing
TEST_REPOS = [
    "rust-lang/mdBook",     # Small Rust project
    "paradigmxyz/reth",     # Ethereum execution client
]