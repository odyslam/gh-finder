"""
Pytest configuration for GitHub Profile Finder tests
"""

import os
import sys
import pytest
import asyncio

# Add the project root to the path for all tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Gather GitHub tokens for tests
@pytest.fixture
def github_tokens():
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

# Create an event loop for asyncio tests
@pytest.fixture
def event_loop():
    """Create an event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# GitHub client fixture
@pytest.fixture
async def github_client(github_tokens):
    """Create a GitHub client for testing."""
    from gh_finder.api.token_manager import TokenManager
    from gh_finder.api.client import GitHubClient
    
    if not github_tokens:
        pytest.skip("No GitHub tokens available for testing")
    
    token_manager = TokenManager(github_tokens, verbose=True)
    client = GitHubClient(
        token=github_tokens[0],
        verbose=True,
        token_manager=token_manager,
        per_page=100
    )
    
    yield client
    
    # Clean up
    await client.close_session()