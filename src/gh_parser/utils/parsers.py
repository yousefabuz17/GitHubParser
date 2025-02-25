import asyncio
import posixpath
import re
from aiohttp import ClientSession, TCPConnector
from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientResponseError,
    ContentTypeError,
    ServerDisconnectedError,
    InvalidURL,
)
from async_lru import alru_cache
from collections import namedtuple, OrderedDict
from configparser import ConfigParser
from functools import cache, cached_property, partial
from itertools import chain
from pathlib import Path


from .endpoints import OTHER_ENDPOINTS
from .exceptions import APIException, ConfigException, GHException
from .type_hints import PathLike
from .utils import _Repr, decode_string, executor, get_parameters, str_instance
from .wrappers import time_wrap, verbose_wrap


# region ConfigFileParser
class ConfigFileParser(ConfigParser):
    """
    A custom `ConfigParser` class that reads and parses configuration files.
    The configuration file contents are stored as a dictionary or nested namedtuples.
    
    ### Parameters:
        - `config_file`: The path to the configuration file.
        - `default_section`: The default section to use in the configuration file.
        - `enhance`: Whether to enhance the configuration file contents.
            ~ If `True`, the configuration file (dictionary) contents \
                will be recursivelsy converted to namedtuples.
        - `*args, **kwargs`: Additional arguments and keyword arguments.
            ~ These are passed to the `ConfigParser` class.
    
    ### Properties (Cached):
        - `config_path` (Posix): The path to the configuration file.
        - `config` (NamedTuple | dict): The parsed configuration file contents.
    
    ### Methods:
        - `format_dict`: Formats the configuration file contents.
            ~ If `enhance` is `True`, the contents are converted to namedtuples.
            ~ The namedtuples are recursively created for nested dictionaries.
        
    ### Exceptions:
        - `ConfigException`: Raised when the configuration file is not found.
            ~ This occurs when the file path is incorrect or the file does not exist \
                in the current working directory.
    
    ### Usage:
        ```python
        from gh_parser import ConfigFileParser
        
        # Initialize the ConfigFileParser class.
        parser = ConfigFileParser("config.ini", enhance=True)
        
        # If 'enhance' is False, the configuration file contents will be a dictionary.
        
        # Get the configuration file contents.
        config = parser.config
        first_header = config.header1
        nested_header = first_header.nested_header
        ```
    
    """

    __slots__: dict = ("_config", "_cf", "_df", "_enhance")

    def __init__(self, config_file: PathLike, *args, **kwargs):
        self._config = None
        self._cf = self._validate_cf(config_file)
        self._df = kwargs.get("default_section")
        self._enhance = kwargs.pop("enhance", False)
        super().__init__(*args, **kwargs)

    def _validate_cf(self, cf: PathLike) -> Path:
        cf = Path(cf).absolute().resolve()
        if not cf.exists():
            raise ConfigException(
                f"Configuration file not found: {cf!r}."
                f"\nEnsure the file path is correct and that the file exists in the specified location."
            )
        return cf

    def _read_cf(self):
        self.read(self._cf)

    @classmethod
    def _format_dict(cls, cf_dict: dict, *, enhance: bool = False):
        match enhance:
            case False:
                cf = {k: {**v} for k, v in cf_dict.items()}
            case True:
                cf_dict = {k.replace(".", "_"): v for k, v in cf_dict.items()}
                _pnt = partial(namedtuple, rename=True)
                main_name = cls.__name__.removesuffix("Parser")
                OuterNT = _pnt(main_name, field_names=(*cf_dict,))
                nts = {
                    k: _pnt(k, field_names=(*v,))(*v.values())
                    for k, v in cf_dict.items()
                }

                cf = OuterNT(**nts)
        return cf

    def _get_config(self):
        self._read_cf()
        cf = dict(self)

        if self._df is None:
            del cf["DEFAULT"]

        new_cf = self._format_dict(cf, enhance=self._enhance)
        return new_cf

    @cached_property
    def config_path(self) -> Path:
        return self._cf

    @cached_property
    def config(self) -> dict:
        if self._config is None:
            self._config = self._get_config()
        return self._config


# region APIParser
class APIParser:
    """
    A custom `APIParser` class that fetches data from the specified URL or API.

    ### Parameters:
        - `url`: The URL to fetch data from.
        - `endpoint`: The endpoint to fetch data from.
        - `headers`: The headers to use for the API request.
        - `json_format`: Whether to format the response as JSON.

    ### Methods:
        - `api_request`: Fetches data from the specified URL.
        - `joinurl`: Joins the specified URL parts.

    ### Properties (Cached):
        - `TTL_DNS` (int): The time-to-live for the DNS cache.
            ~ This is set to 300 seconds by default.
        - `get_contents` (dict): The fetched contents of the API.

    ### Exceptions:
        - `APIException`: Raised when an error occurs in the API request.

    ### Usage:
        ```python
        from gh_parser import APIParser

        # Initialize the APIParser class.
        parser = APIParser(url="https://api.github.com")

        contents = parser.get_contents
        ```

    """

    TTL_DNS: int = 300

    def __init__(
        self,
        *,
        url: str = "",
        endpoint: str = "",
        headers: dict = None,
        json_format: bool = False,
    ):
        self._url = url
        self._endpoint = endpoint
        self._headers = headers or {}
        self._jf = json_format
        self._validate_args()

        self._parsed_contents = None

    def _validate_args(self):
        url, headers, endp, _jf = self._url, self._headers, self._endpoint, self._jf

        if not all(map(str_instance, (url, endp))):
            raise APIException("The URL and endpoint must be strings.")

        if not isinstance(headers, dict):
            raise APIException("The headers must be a dictionary.")

        self._url = "https://" + url.removeprefix("https://")

    @classmethod
    async def api_request(cls, **kwargs):
        cls_params = get_parameters(cls, keys_only=False)
        url, headers, jf = tuple(
            kwargs.get(k, v) for k, v in cls_params.items() if k != "endpoint"
        )

        try:
            async with ClientSession(
                connector=TCPConnector(
                    enable_cleanup_closed=True,
                    ssl=False,
                    force_close=True,
                    ttl_dns_cache=cls.TTL_DNS,
                ),
                raise_for_status=True,
            ) as session:
                async with session.get(url, headers=headers) as response:
                    return await cls._format_response(response, json_format=jf)
        except (ClientResponseError, ContentTypeError) as ccre:
            raise ccre
        except (ClientConnectionError, ServerDisconnectedError):
            return await cls.api_request(url, headers=headers, json_format=jf)
        except InvalidURL:
            raise APIException(f"Invalid URL: {url = }")

    @staticmethod
    @alru_cache
    async def _format_response(response: str, json_format: bool = True):
        return await getattr(response, ["text", "json"][bool(json_format)])()

    @staticmethod
    def joinurl(*args, **kwargs):
        return posixpath.join(*args, **kwargs)

    def _get_contents(self):
        try:
            url_contents = asyncio.run(
                self.api_request(
                    url=self._url, headers=self._headers, json_format=self._jf
                )
            )
        except ClientResponseError:
            # For missing or invalid endpoints.
            url_contents = None
        return url_contents

    @cached_property
    def get_contents(self):
        if self._parsed_contents is None:
            self._parsed_contents = self._get_contents()
        return self._parsed_contents


# region GitHubParser
class GitHubParser(APIParser):
    """
    A custom `APIParser` class that fetches data from the GitHub API.
    The class provides methods to fetch repository statistics, repository contents, and more.

    ### Parameters:
        - `config_file`: The path to the configuration file.
            ~ If provided, the configuration file will be parsed to get the owner, token, repo, or branch.
        - `owner`: The owner of the repository.
        - `repo`: The name of the repository.
        - `branch`: The branch of the repository.
        - `token`: The GitHub API token.
        - `include_empty_files`: Whether to include empty files in the repository.
        - `verbose`: Whether to enable verbose output.

    ### Properties:
        - `branch` (str): The branch of the repository.
        - `full_stats` (dict): The full statistics of the repository.
        - `full_branch` (dict): The full branch data of the owner.
            ~ This includes all the repositories and their contents.
        - `all_repos` (tuple): All the repositories of the owner.
        - `all_repopaths` (tuple): All the paths (files) of the repository.

    ### Methods:
        - `get_path_contents`: Fetches the contents of the specified path.
        - `main_parser`: The main parser for the GitHub API.
        - `rate_limit`: Gets the current GitHub API rate limit.
            ~ `key` (str): The key to retrieve the rate limit data.
                ~ If `key` is not provided, the full rate limit data is returned.
        - `get_path_contents`: Gets the contents of the specified path.
            ~ `path` (str): The path to the file.

    ### Properties (Including Cached):
        - `GITHUB_API` (str): The GitHub API URL (https://api.github.com).
            - `MAIN_API` (str): The main API URL for the repository (/repos/{owner}/{repo}).
            - `REPO_URL` (str): The repository URL (/users/{owner}/repos).
            - `SOURCE_URL` (str): The source URL for the repository contents (/contents/{path}?ref={branch}).
            - `TREE_URL` (str): The tree URL for the repository (/git/trees/{branch}?recursive=1).
            - `OTHER_ENDPOINTS` (tuple): Other endpoints to fetch data from the GitHub API.
        - `MAIN_HEADERS` (dict): The main headers for the GitHub API.
        - `branch`: The branch of the repository.
        - `full_stats`: The full statistics of the repository.
        - `full_branch`: The full branch data of the owner.
        - `all_repos`: All the repositories of the owner.
        - `all_repopaths`: All the paths (files) of the repository.

    ### Exceptions:
        - `GHException`: Raised when an error occurs in the GitHub API.
        - `ConfigException`: Raised when an error occurs in the configuration file.

    ### Usage:
        ```python
        from gh_parser import GitHubParser

        # Initialize the GitHubParser class.
        parser = GitHubParser(owner="owner", repo="repo", token="token")
            ~ The owner, repo, and token can also be provided in the configuration file.
            ~ The configuration file must have a 'github' section with the specified keys.
            ~ E.g., GitHubParser(config_file="config.ini")

        stats = parser.full_stats
        full_branch = parser.full_branch
        all_repos = parser.all_repos
        all_repopaths = parser.all_repopaths
        ```

    """

    GITHUB_API: str = "https://api.github.com"
    MAIN_API: str = GITHUB_API + "/repos/{owner}/{repo}"
    REPO_URL: str = GITHUB_API + "/users/{owner}/repos"
    SOURCE_URL: str = MAIN_API + "/contents/{path}?ref={branch}"
    TREE_URL: str = MAIN_API + "/git/trees/{branch}?recursive=1"
    OTHER_ENDPOINTS: tuple[str, ...] = OTHER_ENDPOINTS
    MAIN_HEADERS: dict = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": "",
    }

    __slots__: tuple[str, ...] = (
        "_owner",
        "_repo",
        "_branch",
        "_token",
        "_include_empty_files",
        "_verbose",
        "_headers",
    )

    def __init__(
        self,
        *,
        config_file: PathLike = "",
        owner: str = "",
        repo: str = "",
        branch: str = "main",
        token: str = "",
        include_empty_files: bool = False,
        verbose=False,
    ):
        if config_file:
            main_keys = ("owner", "token", "repo", "branch")
            parsed_config = ConfigFileParser(config_file, enhance=True).config

            try:
                github_section = parsed_config.github
            except AttributeError:
                raise ConfigException(
                    f"No 'github' section found in the configuration file: {config_file!r}."
                )

            owner, token, repo, branch = map(
                lambda key: getattr(github_section, key, ""), main_keys
            )

        # Class Attributes
        self.OTHER_MAIN_ENDPOINTS: tuple[str, ...] = self._get_main_endpoints()

        # String Arguments
        self._owner = owner
        self._token = token
        self._repo = repo
        self._branch = branch

        # Boolean Arguments
        self._empty_files = include_empty_files
        self._verbose = verbose

        # Validate Arguments
        self._validate_args()

        super().__init__(headers=self._headers, json_format=True)

        # Cached Properties
        self._repos = None
        self._repopaths = None
        self._repo_stats = None
        self._full_branch = None

    @classmethod
    def __call__(cls, **kwargs):
        kwargs.update({"headers": cls.MAIN_HEADERS, "json_format": True})
        parent_parser = cls.__bases__[0]
        return parent_parser(**kwargs)

    @staticmethod
    def _clean_token(token: str) -> str:
        return "token " + token.removeprefix("token ")

    @verbose_wrap("Validating Arguments.")
    def _validate_args(self):
        if not any(
            (str_instance, (self._owner, self._repo, self._branch, self._token))
        ):
            raise GHException(
                f"All {self.__class__.__name__!r} arguments must be type of {str}."
            )

        if not self._owner:
            raise GHException("The owner of the repository must be provided.")

        self._token = self._clean_token(self._token)
        self._headers = self.MAIN_HEADERS

        if self._token:
            self._headers.update({"Authorization": self._token})

    @staticmethod
    def _get_stem(p):
        return Path(p).stem

    @classmethod
    def _get_main_endpoints(cls) -> dict:
        main_api = cls.main_parser(url=cls.GITHUB_API)
        pattern = re.compile(r"^[a-z]+$")
        main_endpoints = {
            k: v for k, v in main_api.items() if pattern.match(cls._get_stem(v))
        }
        return main_endpoints

    def _parse_main_endpoints(self):
        om_endpoints = self.OTHER_MAIN_ENDPOINTS
        zipped_contents = zip(
            om_endpoints,
            executor(lambda url: self.main_parser(url=url), om_endpoints.values()),
        )
        return _Repr(
            (k, ((_k, _v) for _k, _v in v if not _k.endswith("_url")))
            for k, v in zipped_contents
            if v
        )

    def _get_repo_stats(self):
        api_parser = partial(self.main_parser, headers=self._headers)
        url = self.MAIN_API.format(owner=self._owner, repo=self._repo)
        main_stats = api_parser(url=url)
        OTHER_ENDPOINTS = self.OTHER_ENDPOINTS

        if not main_stats:
            raise GHException(
                f"Unable to fetch repository statistics for "
                f"{self._owner + '/' + self._repo!r}."
            )

        stats = (
            (k, v)
            for k, v in main_stats.items()
            if k.endswith("count") or k == "description"
        )

        def _format_endpoint(endp):
            e = next((i for i in OTHER_ENDPOINTS if i.endswith(endp)), "")
            return "-".join(Path(endp).parts[-2:]) if e else endp

        other_urls = (self.joinurl(url, i) for i in OTHER_ENDPOINTS)
        other_exec = executor(lambda u: api_parser(url=u), other_urls)
        other_stats = zip(map(_format_endpoint, OTHER_ENDPOINTS), other_exec)
        full_stats = chain.from_iterable((stats, other_stats))
        return _Repr(full_stats)

    def _main_gh_api(self) -> dict:
        url = self.REPO_URL.format(owner=self._owner)
        response = self.main_parser(url=url, headers=self._headers)
        return response

    @verbose_wrap("Fetching main repository tree.")
    def _main_repotree(self) -> dict:
        url = self.TREE_URL.format(
            owner=self._owner, repo=self._repo, path="", branch=self._branch
        )
        response = self.main_parser(url=url, headers=self._headers)
        return response

    @verbose_wrap("Fetching repository contents from main GitHub API.")
    def _get_repositories(self):
        gh_contents = self._main_gh_api()

        repos = None

        if gh_contents:
            repos = tuple(k["name"] for k in gh_contents)
        return repos

    @verbose_wrap("Fetching repository relative paths.")
    def _get_repo_paths(self):
        main_tree = self._main_repotree()

        repo_paths = None

        def not_hidden(p):
            valid_p = Path(p).parts[-1]
            if valid_p.startswith(".") and not self._include_empty_files:
                return
            return valid_p

        if main_tree:
            tree = main_tree.get("tree")
            if tree is None:
                return
            repo_paths = tuple(k["path"] for k in tree if not_hidden(k["path"]))
        return repo_paths

    @classmethod
    def _new_cls(cls, *args, **kwargs):
        return cls(*args, **kwargs)

    @classmethod
    def _thread_processor(cls, repo=None, **kwargs):
        if repo:
            new_cls = cls._new_cls(repo=repo, **kwargs)
            repo_paths = new_cls.all_repopaths
            return repo, repo_paths, new_cls

    @verbose_wrap("Threading all repositories.")
    def _thread_paths(self):
        repos = self._get_repositories()
        path_contents = OrderedDict()
        main_kwargs = {
            k.strip("_"): v
            for k, v in vars(self).items()
            if k in ("_owner", "_branch", "_token")
        }

        main_executor = executor(
            lambda repo: self._thread_processor(repo=repo, **main_kwargs), repos
        )

        for repo, repopaths, new_cls in main_executor:
            path_contents[repo] = OrderedDict()
            repo_paths = new_cls._get_repo_paths()
            func2 = executor(lambda x: new_cls.get_path_contents(x), repopaths)
            for rp, rp_contents in zip(repo_paths, func2):
                if rp_contents is None and not self._empty_files:
                    # Include empty or non-decodable files.
                    continue
                path_contents[repo][rp] = rp_contents

        return _Repr(path_contents)

    @classmethod
    def main_parser(cls, **kwargs):
        get_contents = kwargs.pop("get_contents", True)
        response = cls.__call__(**kwargs)
        return [response, response.get_contents][get_contents]

    @cache
    def get_path_contents(self, path):
        url = self.SOURCE_URL.format(
            owner=self._owner, repo=self._repo, path=path, branch=self._branch
        )
        response = self.main_parser(url=url, headers=self._headers)
        path_contents = None

        if response:

            def isfile(rcontents):
                try:
                    is_file = rcontents.get("type", False)
                except AttributeError:
                    return isfile(rcontents[0])

                if any((not is_file, is_file != "file")):
                    return
                return rcontents

            file_response = isfile(response)
            if file_response:
                encoded_contents = file_response.get("content")
                if encoded_contents:
                    try:
                        path_contents = decode_string(encoded_contents)
                    except UnicodeDecodeError:
                        pass
                return path_contents

    @cache
    def get_main_page(self, key: str = None):
        main_page = self._parse_main_endpoints()
        return main_page.get(key, main_page)

    @classmethod
    def rate_limit(cls, key: str = None):
        url = cls.joinurl(cls.GITHUB_API, "rate_limit")
        response = cls.main_parser(url=url)

        if key is None or not str_instance(key):
            return response

        key = key.lower()

        main_keys, inner_keys = map(
            lambda k: (*k.keys(),), (response, next(iter(response.values())))
        )
        all_keys = tuple(chain.from_iterable((main_keys, inner_keys)))

        if key not in all_keys:
            raise GHException(
                f"The provided key {key!r} is not a valid option."
                f"\nAvailable keys are: {all_keys}"
            )
        elif key in main_keys:
            return response[key]
        elif key in inner_keys:
            r = lambda x: response[main_keys[x]].get(key)
            return next(filter(bool, map(r, (0, 1))))

    @cached_property
    def branch(self) -> str:
        if self._branch:
            return self._branch

    @cached_property
    def full_stats(self):
        if self._repo_stats is None:
            self._repo_stats = self._get_repo_stats()
        return self._repo_stats

    @cached_property
    @time_wrap
    def full_branch(self):
        if self._full_branch is None:
            self._full_branch = self._thread_paths()
        return self._full_branch

    @cached_property
    def all_repos(self):
        if self._repos is None:
            self._repos = self._get_repositories()
        return self._repos

    @cached_property
    def all_repopaths(self):
        if self._repopaths is None:
            self._repopaths = self._get_repo_paths()
        return self._repopaths


# endregion

__all__ = (
    "APIParser",
    "ConfigFileParser",
    "GitHubParser",
)
