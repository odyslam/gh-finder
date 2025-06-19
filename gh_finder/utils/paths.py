"""
Path utilities for GitHub Profile Finder
"""

import os
from pathlib import Path

# Get project root directory
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# Directories
RUNS_DIR = ROOT_DIR / "runs"
CONFIG_DIR = ROOT_DIR / "config"

def ensure_dir(path):
    """Ensure a directory exists
    
    Args:
        path: Directory path to ensure
    """
    os.makedirs(path, exist_ok=True)
    
def get_config_file_path(filename):
    """Get the path to a config file
    
    Args:
        filename: Config filename
        
    Returns:
        Path: Full path to the config file
    """
    ensure_dir(CONFIG_DIR)
    return CONFIG_DIR / filename 