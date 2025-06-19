"""
Configuration utilities for loading and saving configuration files
"""

import os
import tomli
import tomli_w
import dotenv
from typing import Dict, List, Any, Optional

def load_env_vars() -> List[str]:
    """Load environment variables from .env file
    
    Returns:
        List[str]: GitHub tokens found in environment variables
    """
    # Load .env file into environment variables
    dotenv.load_dotenv()
    
    # Get token(s) from environment
    tokens = []
    
    # First check for GITHUB_TOKENS (multiple tokens separated by comma)
    multi_tokens = os.environ.get('GITHUB_TOKENS')
    if multi_tokens:
        # Make sure to strip any trailing whitespace or newlines
        multi_tokens = multi_tokens.strip()
        tokens_split = multi_tokens.split(',')
        
        for i, token in enumerate(tokens_split):
            clean_token = token.strip()
            if clean_token:
                # Validate token has minimum length
                if len(clean_token) >= 10:
                    tokens.append(clean_token)
                else:
                    print(f"⚠️ Skipping invalid token in GITHUB_TOKENS (too short): {clean_token[:4]}...")
                
    # Then check for single GITHUB_TOKEN
    token = os.environ.get('GITHUB_TOKEN')
    if token and token.strip():
        # Validate token has minimum length
        if len(token.strip()) >= 10:
            # Only add if not already added from GITHUB_TOKENS
            if token.strip() not in tokens:
                tokens.append(token.strip())
        else:
            print(f"⚠️ Skipping invalid GITHUB_TOKEN (too short): {token.strip()[:4]}...")
    
    # Check for individual numbered tokens (GITHUB_TOKEN_1, GITHUB_TOKEN_2, etc.)
    for i in range(1, 10):
        token_name = f"GITHUB_TOKEN_{i}"
        token = os.environ.get(token_name)
        if token and token.strip() and len(token.strip()) >= 10:
            if token.strip() not in tokens:
                tokens.append(token.strip())
    
    # Print debug information about found tokens
    if tokens:
        print(f"✅ Loaded {len(tokens)} token(s) from environment variables")
    
    return tokens

def load_tokens_from_file(filename: str) -> List[str]:
    """Load GitHub tokens from a file, one token per line
    
    Args:
        filename: Path to tokens file
        
    Returns:
        List[str]: GitHub tokens found in the file
    """
    tokens = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    tokens.append(line)
        print(f"✅ Loaded {len(tokens)} tokens from {filename}")
        return tokens
    except Exception as e:
        print(f"❌ Error loading tokens from {filename}: {e}")
        return []

def load_config_file(filename: str) -> Optional[Dict]:
    """Load a TOML configuration file
    
    Args:
        filename: Path to TOML config file
        
    Returns:
        Dict or None: Parsed config or None if file not found/invalid
    """
    try:
        with open(filename, 'rb') as f:
            config = tomli.load(f)
        return config
    except FileNotFoundError:
        print(f"Error: Config file '{filename}' not found")
        return None
    except tomli.TOMLDecodeError:
        print(f"Error: Config file '{filename}' is not a valid TOML file")
        return None
    except Exception as e:
        print(f"Error loading config file: {e}")
        return None

def create_sample_config(filename: str = "repos_config.toml", run_dir: Optional[str] = None) -> str:
    """Create a sample configuration file in TOML format
    
    Args:
        filename: Output filename for the config
        run_dir: Optional directory to create the file in
        
    Returns:
        str: Path to the created config file
    """
    # If run_dir is provided, use it for the file path
    if run_dir:
        filename = os.path.join(run_dir, filename)
    
    config = {
        "repositories": [
            "paradigmxyz/reth",
            {
                "name": "ethereum/go-ethereum",
                "limit": 10,
                "label": "geth"
            },
            {
                "name": "bitcoin/bitcoin",
                "limit": 15,
                "label": "bitcoin-core"
            }
        ]
    }
    
    with open(filename, 'wb') as f:
        tomli_w.dump(config, f)
    
    print(f"✅ Created sample config file: {filename}")
    print("Edit this file to customize the repositories you want to analyze.")
    
    # Also create a sample .env file
    env_file = '.env.sample'
    if run_dir:
        env_file = os.path.join(run_dir, env_file)
    
    with open(env_file, 'w') as f:
        f.write("# GitHub API token (create one at https://github.com/settings/tokens)\n")
        f.write("# Copy this file to .env and add your token\n")
        f.write("# Single token\n")
        f.write("GITHUB_TOKEN=your_github_token_here\n\n")
        f.write("# OR multiple tokens (comma-separated)\n")
        f.write("GITHUB_TOKENS=token1,token2,token3\n")
    
    print(f"✅ Created sample .env file: {env_file}")
    print("Copy to .env and add your GitHub token(s) to avoid rate limits")
    
    return filename 