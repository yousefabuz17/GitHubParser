# GitHubParser

`GitHubParser` is a Python package designed to interact with the GitHub API, providing a suite of tools to fetch and parse data from GitHub repositories. It simplifies the process of accessing repository statistics, contents, and metadata, making it easier for developers to integrate GitHub data into their applications.

## Features
- Fetch Repository Statistics: Retrieve detailed statistics for any GitHub repository.

- Access Repository Contents: Get the contents of specific paths within a repository.

- List All Repositories: Fetch all repositories for a given GitHub user.

- Rate Limit Information: Check the current rate limit status of the GitHub API.

- Configuration File Parsing: Parse configuration files to retrieve GitHub API credentials and other settings.

- Customizable Parsing: Supports custom parsing of URLs and APIs.


## Installation
You can install `GitHubParser` using `pip`:

```bash
pip install gh-parser
```

## Usage
To use `GitHubParser`, you need to create an instance of the `GitHubParser` class and provide your GitHub API credentials. You can then use the various methods provided by the class to fetch and parse data from GitHub repositories.

Here's an example of how you can use `GitHubParser` to fetch statistics for a GitHub repository:

```python
from gh_parser import GitHubParser

# Create an instance of GitHubParser
parser = GitHubParser(owner='<owner>', token='<github_token>')
# Alternatively, you can provide your credentials in a configuration file
parser = GitHubParser(config_file='config.ini')

# Fetch API Information
main_page = parser.get_main_page()

repostats = parser.full_stats

all_repos = parser.all_repos

all_repopaths = parser.all_repopaths

# Alternatively, you can use the custom functions to fetch specific data
from gh_parser import get_repo_stats, get_repo_contents,
get_all_repos, get_rate_limit

# Fetch repository statistics
repo_stats = get_repo_stats(config_file='config.ini')
```
