#!/usr/bin/env python3
"""
Comprehensive test runner for gh-finder
Runs all tests and provides a summary of results
"""

import subprocess
import sys
import time
import os
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

class TestRunner:
    def __init__(self):
        self.results = {}
        self.start_time = time.time()
        
    def print_header(self):
        """Print test runner header"""
        print(f"\n{BOLD}🧪 GitHub Finder Comprehensive Test Suite{RESET}")
        print("=" * 60)
        print(f"Running all tests to ensure the tool works correctly")
        print("=" * 60)
        
    def check_environment(self):
        """Check if environment is properly set up"""
        print(f"\n{BOLD}📋 Environment Check:{RESET}")
        
        # Check for GitHub tokens
        tokens_found = False
        token_count = 0
        
        # Check individual token env vars
        for i in range(1, 10):
            token_env = f"GITHUB_TOKEN_{i}" if i > 1 else "GITHUB_TOKEN"
            if os.getenv(token_env):
                token_count += 1
                tokens_found = True
        
        # Check GITHUB_TOKENS
        tokens_str = os.getenv("GITHUB_TOKENS")
        if tokens_str:
            tokens_found = True
            token_count = max(token_count, len([t.strip() for t in tokens_str.split(",") if t.strip()]))
        
        if tokens_found:
            print(f"{GREEN}✅ Found {token_count} GitHub token(s){RESET}")
        else:
            print(f"{YELLOW}⚠️  No GitHub tokens found - some tests may fail{RESET}")
            print(f"   Set GITHUB_TOKENS environment variable with comma-separated tokens")
        
        # Check for uv
        try:
            subprocess.run(["uv", "--version"], capture_output=True, check=True)
            print(f"{GREEN}✅ uv is installed{RESET}")
        except:
            print(f"{RED}❌ uv is not installed - please install it first{RESET}")
            return False
            
        return True
        
    def run_test(self, test_file, description):
        """Run a single test file"""
        print(f"\n{BOLD}▶️  Running: {description}{RESET}")
        print(f"   File: {test_file}")
        print("-" * 60)
        
        start = time.time()
        
        try:
            # Run the test
            result = subprocess.run(
                ["uv", "run", test_file],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            duration = time.time() - start
            
            if result.returncode == 0:
                self.results[test_file] = {
                    'status': 'passed',
                    'duration': duration,
                    'description': description
                }
                print(f"{GREEN}✅ PASSED{RESET} ({duration:.2f}s)")
                
                # Show key outputs
                if "✅" in result.stdout:
                    success_lines = [line for line in result.stdout.split('\n') if "✅" in line]
                    for line in success_lines[:3]:  # Show first 3 success messages
                        print(f"   {line.strip()}")
                        
            else:
                self.results[test_file] = {
                    'status': 'failed',
                    'duration': duration,
                    'description': description,
                    'error': result.stderr
                }
                print(f"{RED}❌ FAILED{RESET} ({duration:.2f}s)")
                
                # Show error output
                if result.stderr:
                    print(f"{RED}Error output:{RESET}")
                    error_lines = result.stderr.strip().split('\n')
                    for line in error_lines[:10]:  # Show first 10 error lines
                        print(f"   {line}")
                        
        except subprocess.TimeoutExpired:
            duration = time.time() - start
            self.results[test_file] = {
                'status': 'timeout',
                'duration': duration,
                'description': description
            }
            print(f"{YELLOW}⏱️  TIMEOUT{RESET} (exceeded 5 minutes)")
            
        except Exception as e:
            duration = time.time() - start
            self.results[test_file] = {
                'status': 'error',
                'duration': duration,
                'description': description,
                'error': str(e)
            }
            print(f"{RED}💥 ERROR: {e}{RESET}")
            
    def run_all_tests(self):
        """Run all test files"""
        tests = [
            # Core functionality tests
            ("tests/test_tokens.py", "Token Authentication & Rate Limits"),
            ("tests/test_conversion.py", "API Data Conversion"),
            ("tests/test_pr_analysis.py", "Basic PR Analysis"),
            ("tests/test_single_analysis.py", "Comprehensive Profile Analysis"),
            
            # Diagnostic tests
            ("tests/test_pr_details.py", "PR Details & Merger Info"),
            ("tests/test_merger_info_simple.py", "Merger Info Explanation"),
        ]
        
        print(f"\n{BOLD}🚀 Running {len(tests)} test files...{RESET}")
        
        for test_file, description in tests:
            if Path(test_file).exists():
                self.run_test(test_file, description)
            else:
                print(f"\n{YELLOW}⚠️  Skipping {test_file} - file not found{RESET}")
                
    def print_summary(self):
        """Print test summary"""
        total_duration = time.time() - self.start_time
        
        print(f"\n{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}📊 TEST SUMMARY{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}")
        
        passed = sum(1 for r in self.results.values() if r['status'] == 'passed')
        failed = sum(1 for r in self.results.values() if r['status'] == 'failed')
        timeout = sum(1 for r in self.results.values() if r['status'] == 'timeout')
        error = sum(1 for r in self.results.values() if r['status'] == 'error')
        total = len(self.results)
        
        print(f"\nTotal tests run: {total}")
        print(f"{GREEN}✅ Passed: {passed}{RESET}")
        if failed > 0:
            print(f"{RED}❌ Failed: {failed}{RESET}")
        if timeout > 0:
            print(f"{YELLOW}⏱️  Timeout: {timeout}{RESET}")
        if error > 0:
            print(f"{RED}💥 Error: {error}{RESET}")
            
        print(f"\nTotal time: {total_duration:.2f}s")
        
        # Detailed results
        print(f"\n{BOLD}Detailed Results:{RESET}")
        for test_file, result in self.results.items():
            status_icon = {
                'passed': f"{GREEN}✅{RESET}",
                'failed': f"{RED}❌{RESET}",
                'timeout': f"{YELLOW}⏱️{RESET}",
                'error': f"{RED}💥{RESET}"
            }.get(result['status'], '❓')
            
            print(f"{status_icon} {result['description']:<40} ({result['duration']:.2f}s)")
            
        # Overall status
        print(f"\n{BOLD}Overall Status:{RESET}")
        if passed == total:
            print(f"{GREEN}🎉 All tests passed! The tool is ready to use.{RESET}")
            return 0
        else:
            print(f"{RED}⚠️  Some tests failed. Please check the errors above.{RESET}")
            if failed > 0:
                print(f"\nFailed tests:")
                for test_file, result in self.results.items():
                    if result['status'] == 'failed':
                        print(f"  - {result['description']}")
            return 1

def main():
    """Main entry point"""
    runner = TestRunner()
    
    # Print header
    runner.print_header()
    
    # Check environment
    if not runner.check_environment():
        print(f"\n{RED}Environment check failed. Please fix the issues above.{RESET}")
        sys.exit(1)
        
    # Run all tests
    runner.run_all_tests()
    
    # Print summary
    exit_code = runner.print_summary()
    
    print(f"\n{BLUE}💡 Tip: Run individual tests with 'uv run <test_file>' for more details{RESET}")
    print(f"{BLUE}📝 See TEST_README.md for documentation about each test{RESET}\n")
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main() 