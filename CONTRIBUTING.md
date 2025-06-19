# Contributing to GitHub Profile Finder

Thank you for considering contributing to GitHub Profile Finder! This document outlines the process for contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

Before creating bug reports:

1. Check the [issues list](https://github.com/odyslam/gh-finder/issues) for existing reports
2. Ensure you're using the latest version
3. Check if the bug is related to your GitHub token permissions

When reporting a bug, include:

- Clear title and description
- Steps to reproduce the issue
- Expected vs. actual behavior
- Screenshots if applicable
- Environment details (OS, Python version, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating a suggestion:

1. Use a clear and descriptive title
2. Provide a detailed explanation of the suggested enhancement
3. Include examples of how the feature would be used
4. Explain why this enhancement would be useful to most users

### Code Contributions

#### Setting Up Development Environment

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/gh-finder.git`
3. Set up upstream: `git remote add upstream https://github.com/odyslam/gh-finder.git`
4. Create a virtual environment: 
   ```bash
   uv venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
5. Install dependencies in development mode: `uv pip install -e ".[dev]"`

#### Testing

Run tests before submitting your PR:

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_pr_analysis.py

# Run with coverage
pytest --cov=gh_finder tests/
```

#### Pull Requests

1. Create a new branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Run tests to ensure they pass
4. Update documentation if necessary
5. Commit your changes (see commit message guidelines below)
6. Push to your fork: `git push origin feature/my-feature`
7. Create a pull request from your fork to the main repository

#### Commit Message Guidelines

- Use the present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests after the first line
- Consider starting with a type prefix:
  - `feat:` for new features
  - `fix:` for bug fixes
  - `docs:` for documentation changes
  - `style:` for formatting changes
  - `refactor:` for code refactoring
  - `test:` for adding tests
  - `chore:` for maintenance tasks

Example:
```
feat: add GitHub profile scoring feature

Implements a scoring system that evaluates GitHub profiles based on:
- Contribution frequency
- Repository quality
- Cross-repo activity

Fixes #42
```

### Documentation Contributions

Documentation improvements are always welcome. This includes:

- Fixing typos
- Improving explanations
- Adding examples
- Updating the README
- Writing better docstrings

## Project Structure

```
gh-finder/
├── gh_finder/             # Main package
│   ├── api/               # GitHub API interaction
│   ├── core/              # Core functionality
│   ├── models/            # Data models
│   └── utils/             # Utility functions
├── tests/                 # Test suite
├── runs/                  # Created during execution for outputs
└── checkpoints/           # Created during execution for state
```

### Key Components

- **TokenManager**: Handles GitHub API token rotation and rate limiting
- **GitHubClient**: Wraps PyGithub with better token management
- **ProfileAnalyzer**: Analyzes GitHub user profiles
- **ProfileFinder**: Finds contributors in repositories
- **ProfileEvaluator**: Scores and categorizes profiles

## Coding Standards

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guidelines
- Use type hints where appropriate
- Write docstrings for all public functions, classes, and methods
- Keep functions focused on a single responsibility
- Add tests for new functionality

## License

By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).

## Questions?

Feel free to create an issue if you have any questions about contributing!