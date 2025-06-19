# GitHub Finder Test Suite

This directory contains test scripts to verify the functionality of the GitHub Finder tool.

## Quick Start

### 1. Verify Installation

First, check that everything is properly installed:

```bash
uv run verify_installation.py
```

This will check:
- Python version (3.8+)
- uv installation
- gh-finder package installation
- GitHub tokens configuration
- Required files and directories

### 2. Run All Tests
The easiest way to run all tests with a comprehensive summary:

```bash
# Using the comprehensive test runner (recommended)
uv run run_all_tests.py

# Or use the interactive menu
./run_tests.sh
# Then choose option 4
```

## Test Files

### Core Functionality Tests

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

### Diagnostic Tests

5. **test_pr_details.py** - PR Details & Merger Info
   - Examines PR merger patterns
   - Analyzes missing merger information
   - Tests detailed PR API calls

6. **test_merger_info_simple.py** - Merger Info Explanation
   - Explains why merger info is sometimes missing
   - Provides examples from popular repositories
   - Educational test about GitHub API limitations

## Running Individual Tests

You can run any test individually:

```bash
# Basic PR analysis
uv run test_pr_analysis.py

# Comprehensive test suite
uv run test_single_analysis.py

# Token validation
uv run test_tokens.py
```

## Test Runners

### run_all_tests.py
Comprehensive test runner that:
- Runs all tests in sequence
- Provides colored output
- Shows progress for each test
- Generates a summary report
- Returns proper exit codes for CI/CD

### run_tests.sh
Interactive test runner with menu:
- Option 1: Quick PR analysis test
- Option 2: Comprehensive test suite
- Option 3: Both tests above
- Option 4: All tests with summary (calls run_all_tests.py)

### verify_installation.py
Pre-flight check script that verifies:
- Python version compatibility
- uv package manager installation
- gh-finder package installation
- GitHub tokens configuration
- Required directories and files

## Troubleshooting

### "No GitHub token found!"
Make sure you have set your GitHub token(s) as environment variables:
```bash
export GITHUB_TOKEN="your-token-here"
# or for multiple tokens:
export GITHUB_TOKEN_1="first-token"
export GITHUB_TOKEN_2="second-token"
```

### "AttributeError: 'GitHubProfile' object has no attribute..."
This means there's a mismatch in the data model. The comprehensive test will help identify which attributes are missing.

### Rate Limit Warnings
If you see rate limit warnings, the test will still run but you may want to wait before running the full analysis.

### Missing Merger Information

If you see warnings about missing merger info, this is normal. Common reasons:
- Deleted GitHub accounts
- Bot mergers (GitHub Actions, merge bots)
- Legacy data from older PRs
- API limitations

Run `test_merger_info_simple.py` for a detailed explanation.

## CI/CD Integration

To use in CI/CD pipelines:

```bash
# Run all tests and exit with proper code
uv run run_all_tests.py

# Exit code 0 = all tests passed
# Exit code 1 = some tests failed
```

## What Gets Tested

### Data Models
- `GitHubProfile` - User profile data structure
- `ProfileEvaluation` - Scoring and categorization
- `Repository`, `LanguageDetail`, `MergedPRDetail` - Supporting data structures

### Core Components
- `GitHubClient` - API communication with PyGithub
- `GitHubProfileAnalyzer` - User profile analysis
- `ProfileEvaluator` - Profile scoring and evaluation
- `GitHubProfileFinder` - Repository and contributor analysis
- `CheckpointManager` - State persistence

### Functionality
- Fetching user profiles from GitHub
- Analyzing user repositories and languages
- Detecting PR mergers in repositories
- Finding quality fork contributors
- Evaluating profiles with scoring system
- Saving and loading checkpoints

## Expected Output

When running `test_pr_analysis.py`, you should see output like:
```
🧪 GitHub PR Analysis Test
✅ Found GitHub token
✅ Rate limit: 4950/5000 requests remaining

🔍 Testing PR fetching for rust-lang/mdBook
✅ Fetched 100 PRs from page 1
📊 PR Analysis Results:
   - Merged PRs: 87
   - Closed (not merged) PRs: 13
   - Unique mergers found: 12

👥 Top PR Mergers:
   - @ehuss: 45 PRs
   - @Dylan-DPC: 15 PRs
   ...
```

## Next Steps

Once all tests pass:
1. Review the test output to ensure data looks correct
2. Check that PR mergers are being detected properly
3. Verify profile evaluation scores make sense
4. Run the full analysis with confidence:
   ```bash
   uv run gh_finder.py --config repos_config.toml --analyze-prs
   ``` 