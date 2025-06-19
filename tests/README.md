# GitHub Profile Finder Tests

This directory contains tests for verifying the functionality of the GitHub Profile Finder tool. The tests are organized to make it easy to run individually or as a complete suite.

## Quick Start

### Running All Tests

```bash
# Run all tests with pytest
pytest

# Run with coverage
pytest --cov=gh_finder tests/

# Run the comprehensive test runner
uv run run_all_tests.py
```

### Running Individual Tests

```bash
# Basic PR analysis
pytest tests/test_pr_analysis.py

# Token management
pytest tests/test_tokens.py

# API data conversion
pytest tests/test_conversion.py
```

## Test Structure

### Core Test Files

1. **test_tokens.py** - Token Authentication & Rate Limits
   - Validates GitHub token authentication
   - Checks rate limit status for each token
   - Tests token rotation functionality

2. **test_conversion.py** - API Data Conversion
   - Tests PyGithub object to dictionary conversion
   - Validates rate limit data extraction
   - Ensures proper data format handling

3. **test_pr_analysis.py** - Basic PR Analysis
   - Tests fetching PRs from a repository
   - Validates PR data structure
   - Checks basic PR analysis functionality

4. **test_single_analysis.py** - Comprehensive Profile Analysis
   - Tests complete user profile analysis
   - Validates profile scoring and evaluation
   - Tests checkpoint save/load functionality
   - Comprehensive integration test

5. **test_pr_details.py** - PR Details & Merger Info
   - Examines PR merger patterns
   - Analyzes missing merger information
   - Tests detailed PR API calls

6. **test_merger_info_simple.py** - Merger Info Explanation
   - Explains why merger info is sometimes missing
   - Provides examples from popular repositories
   - Educational test about GitHub API limitations

### Supporting Files

- **conftest.py** - Pytest configuration and fixtures
- **test_helpers.py** - Common test utilities and helper functions
- **run_all_tests.py** - Comprehensive test runner (in project root)

## GitHub Token Configuration

Tests require a GitHub token to run. You can provide it in several ways:

```bash
# Environment variable
export GITHUB_TOKEN="your-token-here"

# For multiple tokens
export GITHUB_TOKENS="token1,token2,token3"

# Individual numbered tokens
export GITHUB_TOKEN_1="token1"
export GITHUB_TOKEN_2="token2"
```

## Writing New Tests

When adding new tests:

1. Use the fixtures from `conftest.py` when possible
2. Use helper functions from `test_helpers.py` for common operations
3. Add both assertion-based tests (for pytest) and print-based output (for users)
4. Make sure tests can run individually and as part of the suite
5. Add the test to `run_all_tests.py` if it's a major test

Example new test file:

```python
#!/usr/bin/env python3
"""
Test description here
"""

import asyncio
import pytest
from test_helpers import (
    print_test_header, 
    print_test_section, 
    check_rate_limit,
    TEST_REPOS
)

@pytest.mark.asyncio
async def test_my_feature(github_client):
    """Test my new feature"""
    print_test_section("Testing my feature")
    
    # Test code here
    result = await github_client.some_function()
    
    # Assertions for pytest
    assert result is not None
    assert len(result) > 0
    
    # Print results for users
    print(f"✅ Feature returned {len(result)} items")
    
    return True

# Optional: Command-line test runner
async def main():
    """Main function for direct execution"""
    # Setup similar to other test files
    # ...

if __name__ == "__main__":
    asyncio.run(main())
```

## Troubleshooting Tests

### Rate Limit Issues

If you encounter rate limit issues during testing:

1. Use fewer tests or add more tokens
2. Look for rate limit warnings in the test output
3. Wait for rate limits to reset before running tests again

### Missing Token

If you see "No GitHub token found!" errors:

```bash
# Check if token is set
echo $GITHUB_TOKEN

# If not, set it
export GITHUB_TOKEN="your-token-here"
```

### Integration Test Failures

For failures in integration tests:

1. Run the specific failing test with detailed output
2. Check GitHub API status for service issues
3. Verify token permissions (need `repo` scope for private repos)