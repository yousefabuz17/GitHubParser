from .utils.parsers import ConfigFileParser, GitHubParser
from .utils.type_hints import Any, PathLike, Union
from .utils.wrappers import func_wrap


func_wrapper = lambda attr: func_wrap(attr, cls_obj=GitHubParser)


def parse_url(**kwargs) -> Any:
    return GitHubParser.main_parser(**kwargs)


def parse_config(config_file: PathLike, full_config: bool = True) -> Union[ConfigFileParser, dict]:
    cfg = ConfigFileParser(config_file)
    return [cfg, cfg.config][full_config]


def get_rate_limit(key: str = None) -> Union[dict, int]:
    return GitHubParser.rate_limit(key=key)


@func_wrapper("full_stats")
def get_repo_stats(*args, **kwargs) -> dict:
    pass


@func_wrapper("all_repos")
def get_all_repos(*args, **kwargs) -> dict:
    pass


@func_wrapper("all_repopaths")
def get_all_repopaths(*args, **kwargs) -> dict:
    pass


@func_wrapper("full_branch")
def get_full_branch(*args, **kwargs) -> dict:
    pass


def get_path_contents(*args, **kwargs) -> str:
    path = kwargs.pop("path", None)
    return GitHubParser(*args, **kwargs).get_path_contents(path=path)


__all__ = tuple(
    k
    for k in globals()
    if k.startswith(("get", "parse"))
)