#!/usr/bin/env python3
"""
Wrapper script for backward compatibility with the original gh_finder.py script.
This script just forwards to the new modular package.
"""

import sys
import os
import dotenv

# Make sure we load environment variables before importing the main module
# This ensures .env tokens are available to all components
dotenv.load_dotenv()

from gh_finder.main import main

if __name__ == "__main__":
    # Run the main program
    # No debugging output needed now that token loading is fixed
    
    main()
