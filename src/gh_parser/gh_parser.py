from .utils.parsers import APIParser, ConfigFileParser, GitHubParser
from .utils.type_hints import Any, LiteralInt, PathLike, Union
from .utils.wrappers import func_wrap


func_wrapper = lambda attr: func_wrap(attr, cls_obj=GitHubParser)


def parse_url(**kwargs) -> Any:
    return GitHubParser.main_parser(**kwargs)


def parse_config(
    config_file: PathLike, *args, **kwargs
) -> Union[ConfigFileParser, dict]:
    parser_only = kwargs.pop("parser_only", False)
    cfg = ConfigFileParser(config_file, *args, **kwargs)
    return [cfg.config, cfg][parser_only]


def get_parser(index: LiteralInt):
    return (APIParser, ConfigFileParser, GitHubParser)[index]


def get_rate_limit(key: str = None) -> Union[dict, int]:
    return GitHubParser.rate_limit(key=key)


@func_wrapper("full_stats")
def get_repo_stats(**kwargs) -> dict:
    pass


@func_wrapper("all_repos")
def get_all_repos(**kwargs) -> dict:
    pass


@func_wrapper("all_repopaths")
def get_all_repopaths(**kwargs) -> dict:
    pass


@func_wrapper("full_branch")
def get_full_branch(**kwargs) -> dict:
    pass


def get_path_contents(**kwargs) -> str:
    path = kwargs.pop("path", None)
    return GitHubParser(**kwargs).get_path_contents(path=path)


def get_metadata(enhance: bool = True):
    parser = parse_config("setup.cfg", enhance=enhance)
    if enhance:
        metadata = parser.metadata
    else:
        metadata = parser["metadata"]
    return metadata


__all__ = tuple(k for k in globals() if k.startswith(("get", "parse"))) + (
    "APIParser",
    "ConfigFileParser",
    "GitHubParser",
)
