# 🔍 GitHub Profile Finder

<p align="center">
  <strong>Discover talented developers by analyzing their GitHub contributions to your target repositories</strong>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-installation">Installation</a> •
  <a href="#-usage">Usage</a> •
  <a href="#-configuration">Configuration</a> •
  <a href="#-api-optimization">API Optimization</a>
</p>

---

## 🎯 Overview

GitHub Profile Finder is a powerful tool designed to help you identify and evaluate potential developer candidates by analyzing their contributions to specific repositories. Whether you're looking for Rust experts, blockchain developers, or contributors to specific projects, this tool automates the discovery process while respecting GitHub API rate limits.

### 🚀 Perfect For:

- **Recruiters** seeking developers with specific technical expertise
- **Open Source Projects** looking for experienced contributors
- **Companies** building teams around specific technologies
- **Researchers** analyzing developer communities

## ✨ Features

### 🧠 Smart Analysis Modes

#### **Hybrid Approach** (Recommended)

- **Tier 0-1 repos**: Analyzes actual PR mergers (highest quality signal)
- **Tier 2+ repos**: Uses fork analysis with quality filters (API-friendly)
- Automatically optimizes API usage based on repository importance

#### **Fork Analysis** 

- Identifies developers who have forked and actively maintain repositories
- Filters by stars, recent activity, and meaningful changes
- 30x more API-efficient than PR analysis

#### **PR Analysis**

- Finds developers who have successfully merged PRs
- Highest quality signal for proven contributors
- Best for critical repositories where quality matters most

### 🎨 Advanced Features

- **🤖 LLM Integration**: Generate AI-ready reports for deeper candidate analysis
- **💾 Checkpoint System**: Resume interrupted scans without losing progress
- **🔄 Multi-Token Support**: Rotate through multiple GitHub tokens automatically
- **📊 Tiered Repository System**: Prioritize important repositories
- **🎯 Progressive Rate Limiting**: Smart API usage based on repository tier
- **📈 Comprehensive Scoring**: Evaluate developers on multiple dimensions

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/odyslam/gh-finder.git
cd gh-finder

# Install with uv (recommended)
uv pip install -e .

# Run your first analysis
./run.py --config repos_config.toml --token YOUR_GITHUB_TOKEN --analyze-prs
```

## 📦 Installation

### Prerequisites

- Python 3.8+
- GitHub Personal Access Token(s)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Detailed Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/odyslam/gh-finder.git
   cd gh-finder
   ```

2. **Install dependencies**

   ```bash
   # Using uv (recommended)
   uv pip install -e .
   
   # Or using pip
   pip install -e .
   ```

3. **Set up your GitHub token**

   ```bash
   # Option 1: Environment variable
   export GITHUB_TOKEN="your_token_here"
   
   # Option 2: Pass directly
   ./run.py --token YOUR_TOKEN --config repos_config.toml
   
   # Option 3: Use multiple tokens
   echo "token1" > tokens.txt
   echo "token2" >> tokens.txt
   ./run.py --tokens-file tokens.txt --config repos_config.toml
   ```

## 📖 Usage

### Basic Commands

```bash
# Analyze repositories with smart hybrid approach
./run.py --config repos_config.toml --token YOUR_TOKEN --analyze-prs

# Fork-only analysis (API-friendly, quick discovery)
./run.py --config repos_config.toml --token YOUR_TOKEN

# Analyze with limits
./run.py --config repos_config.toml --token YOUR_TOKEN --limit 100

# Resume from latest checkpoint (across all runs)
./run.py --config repos_config.toml --token YOUR_TOKEN --resume latest

# Resume from a specific run (uses latest checkpoint in that run)
./run.py --config repos_config.toml --token YOUR_TOKEN --resume 20250115_143022

# Generate LLM analysis
./run.py --config repos_config.toml --token YOUR_TOKEN --llm-output auto

# Check all tokens' rate limit status
./run.py --tokens-file tokens.txt --check-tokens
```

### Advanced Options

| Flag | Description |
|------|-------------|
| `--analyze-prs` | Enable PR analysis for high-tier repos |
| `--verbose` | Show detailed progress information |
| `--limit N` | Limit analysis to N users per repository |
| `--resume latest` | Resume from the most recent checkpoint |
| `--resume RUN_NAME` | Resume from specific run (e.g., `--resume 20250115_143022`) |
| `--force-reanalyze` | Re-analyze previously processed repos |
| `--llm-output [console\|auto\|filename]` | Generate LLM-friendly analysis |
| `--list-checkpoints` | Show available checkpoints organized by run |
| `--check-tokens` | Check all GitHub API tokens rate limit status |

### 🤖 LLM Analysis

Generate comprehensive reports for AI-powered analysis:

```bash
# Quick demo
./llm_analysis_example.py YOUR_TOKEN

# Full analysis with auto-named output
./run.py --config repos_config.toml --token YOUR_TOKEN --llm-output auto

# Output to console for immediate copying
./run.py --config repos_config.toml --token YOUR_TOKEN --llm-output console
```

Then paste the output into Claude, GPT-4, or other LLMs with prompts like:
- *"Which developers would excel at optimizing a Rust EVM implementation?"*
- *"Find candidates with deep systems programming experience who might be open to new opportunities"*
- *"Identify the top 5 developers based on contribution quality and technical fit"*

## ⚙️ Configuration

### Repository Configuration

Create a TOML file organizing repositories by priority tiers:

```toml
# repos_config.toml
repositories = [
    # Tier 0: Highest Priority (PR analysis when enabled)
    [
        { name = "paradigmxyz/reth", label = "Reth - Rust Ethereum Client" },
        { name = "bluealloy/revm", label = "REVM - Rust EVM" }
    ],
    
    # Tier 1: High Priority (PR analysis when enabled)
    [
        { name = "foundry-rs/foundry", label = "Foundry - Ethereum Dev Tools" },
        { name = "gakonst/ethers-rs", label = "Ethers-rs - Ethereum SDK" }
    ],
    
    # Tier 2+: Standard Priority (Fork analysis with quality filters)
    [
        { name = "solana-labs/solana", label = "Solana Core" },
        { name = "paritytech/substrate", label = "Substrate Framework" }
    ]
]
```

### Progressive Limits by Tier

The tool automatically adjusts limits based on repository importance:

| Tier | PR Analysis | Fork Analysis | Fork Limit |
|------|-------------|---------------|------------|
| 0-1 | ✅ Enabled | If PRs disabled | Unlimited |
| 2 | ❌ Disabled | ✅ Enabled | 200 |
| 3 | ❌ Disabled | ✅ Enabled | 150 |
| 4+ | ❌ Disabled | ✅ Enabled | 30-100 |

## 🔧 API Optimization

### Rate Limit Management

- **Automatic Token Rotation**: Seamlessly switches between tokens when limits are reached
- **Smart Checkpointing**: Saves progress before API exhaustion
- **Progressive Backoff**: Reduces API usage for lower-priority repositories

### API Usage Tips

1. **Start Small**: Test with 1-2 repositories first
2. **Use Multiple Tokens**: Distribute load across tokens
   ```bash
   ./run.py --tokens-file tokens.txt --config repos_config.toml
   ```
3. **Monitor Rate Limits**: Use `--verbose` to see remaining API calls
4. **Fork Analysis First**: Use fork-only mode for initial discovery
5. **PR Analysis for Validation**: Reserve PR analysis for top candidates

## 📊 Understanding the Output

### Profile Categories

- **🏆 Tier 0/1 Rust Core Contributor**: Has merged PRs in your highest priority repos
- **⭐ Core Target Repo Contributor**: Active contributor across multiple target repos
- **💎 Strong Rust Developer**: Primary Rust user with high overall score
- **✨ Top Developer**: High score regardless of specific language
- **📍 Cross-Target Contributor**: Appears in multiple target repositories

### Evaluation Metrics

| Metric | Weight | Description |
|--------|--------|-------------|
| Rust Expertise | 30% | Proficiency in Rust programming |
| PR Contributions | 30% | Quality and quantity of merged PRs |
| Cross-Repo Activity | 10% | Contributions across multiple targets |
| General Activity | 10% | Overall GitHub activity and recency |
| Account Maturity | 5% | Account age and consistency |
| Repository Quality | 5% | Personal project quality |
| Follower Count | 5% | Community recognition |
| Openness Signals | 5% | Job search indicators |

## 📁 Repository Structure

- `gh_finder/` - Main package code
- `tests/` - Test suite
- `utils/` - Utility scripts and tools
  - `check/` - Verification and token checking tools
  - `debug/` - Debugging utilities
  - `examples/` - Example usage scripts
  - `scripts/` - Test and run scripts

## 🐛 Troubleshooting

### Common Issues

**Rate Limit Errors**
```bash
# Check all tokens status
./run.py --tokens-file tokens.txt --check-tokens

# Solution: Add more tokens
echo "token1" > tokens.txt
echo "token2" >> tokens.txt
./run.py --tokens-file tokens.txt --config repos_config.toml
```

When all tokens are exhausted, the tool will:
- ✅ Automatically check all tokens' status
- 📊 Display remaining API calls for each token
- ⏰ Show exactly when tokens will reset
- 💾 Create a checkpoint before stopping
- 💡 Provide the exact command to resume later

**Checkpoint Not Found**
```bash
# List available checkpoints organized by run
./run.py --list-checkpoints

# Resume from a specific run (latest checkpoint in that run)
./run.py --resume 20250115_143022 --config repos_config.toml

# Use specific checkpoint file
./run.py --resume checkpoint_20250115_143022.json --config repos_config.toml
```

**Memory Issues with Large Repos**
```bash
# Use limits to control memory usage
./run.py --config repos_config.toml --token YOUR_TOKEN --limit 50
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

Built with ❤️ using:
- [PyGithub](https://github.com/PyGithub/PyGithub) - GitHub API v3 Python client
- [Rich](https://github.com/Textualize/rich) - Beautiful terminal formatting
- [TOML](https://github.com/uiri/toml) - Configuration file parsing
- [Claude](https://claude.ai) - Primary Developer

---

<p align="center">
  Made by <a href="https://github.com/odyslam">@odyslam</a> • 
  <a href="https://github.com/odyslam/gh-finder/issues">Report Bug</a> • 
  <a href="https://github.com/odyslam/gh-finder/pulls">Contribute</a>
</p>