#!/usr/bin/env python3
"""
Quick verification script to check if gh-finder is properly installed and configured
"""

import os
import sys
import subprocess
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'

def check_item(description, check_func):
    """Check an item and print result"""
    try:
        result, message = check_func()
        if result:
            print(f"{GREEN}✅ {description}{RESET}")
            if message:
                print(f"   {message}")
        else:
            print(f"{RED}❌ {description}{RESET}")
            if message:
                print(f"   {message}")
        return result
    except Exception as e:
        print(f"{RED}❌ {description}{RESET}")
        print(f"   Error: {e}")
        return False

def check_python():
    """Check Python version"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return False, f"Python {version.major}.{version.minor} (need 3.8+)"

def check_uv():
    """Check if uv is installed"""
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "uv not found"
    except:
        return False, "uv not installed"

def check_package():
    """Check if gh-finder package is installed"""
    try:
        import gh_finder
        return True, f"Package found at {gh_finder.__file__}"
    except ImportError:
        return False, "Package not installed - run 'uv pip install -e .'"

def check_tokens():
    """Check GitHub tokens"""
    token_count = 0
    sources = []
    
    # Check individual tokens
    for i in range(1, 10):
        token_env = f"GITHUB_TOKEN_{i}" if i > 1 else "GITHUB_TOKEN"
        if os.getenv(token_env):
            token_count += 1
            sources.append(token_env)
    
    # Check GITHUB_TOKENS
    tokens_str = os.getenv("GITHUB_TOKENS")
    if tokens_str:
        tokens = [t.strip() for t in tokens_str.split(",") if t.strip()]
        if tokens:
            token_count = max(token_count, len(tokens))
            sources.append("GITHUB_TOKENS")
    
    if token_count > 0:
        return True, f"Found {token_count} token(s) from: {', '.join(sources)}"
    return False, "No tokens found - set GITHUB_TOKENS environment variable"

def check_config():
    """Check if repos_config.toml exists"""
    if Path("repos_config.toml").exists():
        return True, "repos_config.toml found"
    return False, "repos_config.toml not found"

def check_directories():
    """Check required directories"""
    dirs = ["gh_finder", "runs"]
    existing = [d for d in dirs if Path(d).exists()]
    if len(existing) == len(dirs):
        return True, f"All directories present: {', '.join(dirs)}"
    missing = [d for d in dirs if d not in existing]
    return False, f"Missing directories: {', '.join(missing)}"

def main():
    print(f"\n{BOLD}🔍 GitHub Finder Installation Verification{RESET}")
    print("=" * 50)
    
    checks = [
        ("Python 3.8+", check_python),
        ("uv installed", check_uv),
        ("gh-finder package", check_package),
        ("GitHub tokens", check_tokens),
        ("Configuration file", check_config),
        ("Required directories", check_directories),
    ]
    
    results = []
    for description, check_func in checks:
        results.append(check_item(description, check_func))
    
    print("\n" + "=" * 50)
    
    if all(results):
        print(f"{GREEN}{BOLD}✅ All checks passed!{RESET}")
        print(f"\n{BOLD}Next steps:{RESET}")
        print("1. Run tests: ./run_tests.sh (choose option 4)")
        print("2. Run the tool: uv run gh_finder.py --config repos_config.toml --analyze-prs")
    else:
        print(f"{RED}{BOLD}⚠️  Some checks failed{RESET}")
        print(f"\n{BOLD}Please fix the issues above before running the tool.{RESET}")
        
        if not results[1]:  # uv not installed
            print(f"\n{YELLOW}Install uv:{RESET}")
            print("  curl -LsSf https://astral.sh/uv/install.sh | sh")
            
        if not results[2]:  # package not installed
            print(f"\n{YELLOW}Install package:{RESET}")
            print("  uv pip install -e .")
            
        if not results[3]:  # no tokens
            print(f"\n{YELLOW}Set GitHub tokens:{RESET}")
            print("  export GITHUB_TOKENS='token1,token2,token3'")

if __name__ == "__main__":
    main() 