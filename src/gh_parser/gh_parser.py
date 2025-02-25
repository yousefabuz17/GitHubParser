from .utils.parsers import APIParser, ConfigFileParser, GitHubParser
from .utils.type_hints import Any, LiteralInt, PathLike, Union
from .utils.wrappers import func_wrap


gh_wrapper = lambda attr: func_wrap(attr, cls_obj=GitHubParser)


# region parse_config
def parse_config(config_file: PathLike, **kwargs) -> Union[ConfigFileParser, dict]:
    """
    Parse the contents of a configuration file.

    ### Parameters:
        - `config_file`: The path to the configuration file.
        - `parser_only`: Whether to return the ConfigFileParser object.
        - `kwargs`: The keyword arguments to pass to the ConfigParser object.

    ### Returns:
        - The configuration dictionary or the ConfigFileParser
    """
    parser_only = kwargs.pop("parser_only", False)
    cfg = ConfigFileParser(config_file, **kwargs)
    return [cfg.config, cfg][parser_only]


# ------------------------------------------------------------

#       The following functions are used in the CLI script.

# ------------------------------------------------------------


# region parse_url
@func_wrap("get_contents", APIParser)
def parse_url(**kwargs) -> Any:
    """
    Parse the contents of a URL or API.

    :param kwargs: The keyword arguments to pass to the APIParser object.
    :type kwargs: dict
    :return: The contents of the URL or API.
    :rtype: Any
    """
    pass


# region get_parser
def get_parser(index: LiteralInt):
    """
    Get the parser object based on the index provided.

    :param index: The index of the parser object to return.
    :type index: int
    :return: The parser object.
    :rtype: Union[APIParser, ConfigFileParser, GitHubParser]
    """
    return (APIParser, ConfigFileParser, GitHubParser)[index]


# region get_rate_limit
def get_rate_limit(key: str = None) -> Union[dict, int]:
    """
    Get the current rate limit of the GitHub API.

    :param key: The key to retrieve from the rate limit dictionary.
    :type key: str
    :return: The rate limit dictionary or the value of the key provided.
    :rtype: Union[dict, int]
    """
    return GitHubParser.rate_limit(key=key)


# region get_path_contents
def get_path_contents(**kwargs) -> str:
    """
    Get the contents of a GitHub repository path.

    :param kwargs: The keyword arguments to pass to the GitHubParser object.
    :type kwargs: dict
    :return: The contents of the path.
    :rtype: str
    """
    path = kwargs.pop("path", None)
    return GitHubParser(**kwargs).get_path_contents(path=path)


# region get_metadata
def get_metadata(enhance: bool = True):
    """
    Get the metadata for `gh_parser` from the setup.cfg file.

    :param enhance: Whether to enhance the metadata with nested namedtuples.
    :type enhance: bool
    :return: The metadata dictionary.
    :rtype: dict
    """
    parser = parse_config("setup.cfg", enhance=enhance)
    return getattr(parser, "metadata", parser["metadata"])


# region get_main_page
def get_main_page(**kwargs):
    """
    Get the main page of a GitHub owner.
    
    :param kwargs: The keyword arguments to pass to the GitHubParser object.
    :type kwargs: dict
    :return: The main page of the owner.
    :rtype: dict
    """
    key = kwargs.pop("key", None)
    return GitHubParser(**kwargs).get_main_page(key=key)


# region get_repo_stats
@gh_wrapper("full_stats")
def get_repo_stats(**kwargs) -> dict:
    """
    Get the statistics for a GitHub repository.

    :param kwargs: The keyword arguments to pass to the GitHubParser object.
    :type kwargs: dict
    :return: The statistics for the repository.
    :rtype: dict
    """
    pass


# region get_all_repos
@gh_wrapper("all_repos")
def get_all_repos(**kwargs) -> dict:
    """
    Get all the repositories for a GitHub user.

    :param kwargs: The keyword arguments to pass to the GitHubParser object.
    :type kwargs: dict
    :return: The repositories for the owner.
    :rtype: dict
    """
    pass


# region get_all_repopaths
@gh_wrapper("all_repopaths")
def get_all_repopaths(**kwargs) -> dict:
    """
    Get all the paths (files) for a GitHub repository.

    :param kwargs: The keyword arguments to pass to the GitHubParser object.
    :type kwargs: dict
    :return: The paths for the repository.
    :rtype: dict
    """
    pass


# region get_full_branch
@gh_wrapper("full_branch")
def get_full_branch(**kwargs) -> dict:
    """
    Get the full branch data for a GitHub repository.

    :param kwargs: The keyword arguments to pass to the GitHubParser object.
    :type kwargs: dict
    :return: The full branch data.
    :rtype: dict
    """
    pass


# endregion


__all__ = tuple(k for k in globals() if k.startswith(("get", "parse"))) + (
    "APIParser",
    "ConfigFileParser",
    "GitHubParser",
)
