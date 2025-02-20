import asyncio
import posixpath
from aiohttp import ClientSession, TCPConnector
from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientResponseError,
    ContentTypeError,
    ServerDisconnectedError,
    InvalidURL,
)
from async_lru import alru_cache
from collections import OrderedDict
from configparser import ConfigParser
from functools import cache, cached_property, partial
from itertools import chain
from pathlib import Path


from .exceptions import APIException, GHException
from .type_hints import PathLike
from .utils import _Repr, decode_string, executor, get_parameters, str_instance
from .wrappers import time_wrap, verbose_wrap


# region ConfigFileParser
class ConfigFileParser(ConfigParser):
    def __init__(self, config_file: PathLike, *args, **kwargs):
        self._config = None
        self._cf = config_file
        self._df = kwargs.get("default_section", None)
        super().__init__(*args, **kwargs)

    def _read_cf(self):
        self.read(self._cf)

    @staticmethod
    def _format_cf(cf_dict):
        cf = {k.lower(): {h: s for h, s in v.items()} for k, v in cf_dict.items()}
        return cf

    def _get_config(self):
        self._read_cf()
        cf = dict(self)

        if self._df is None:
            del cf["DEFAULT"]

        new_cf = self._format_cf(cf)
        return new_cf

    @cached_property
    def config_path(self) -> Path:
        return Path(self._cf).absolute().resolve()

    @cached_property
    def config(self) -> dict:
        if self._config is None:
            self._config = self._get_config()
        return self._config


# region APIParser
class APIParser:
    TTL_DNS: int = 300

    def __init__(
        self,
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

        self._api_contents = None

    def _validate_args(self):
        url, headers, endp, _jf = self._url, self._headers, self._endpoint, self._jf

        if not all(map(str_instance, (url, endp))):
            raise APIException("The URL and endpoint must be strings.")

        if not isinstance(headers, dict):
            raise APIException("The headers must be a dictionary.")

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
            url_contents = None
        return url_contents

    @cached_property
    def api_contents(self):
        if self._api_contents is None:
            self._api_contents = self._get_contents()
        return self._api_contents


# region GitHubParser
class GitHubParser(APIParser):
    GITHUB_API: str = "https://api.github.com"
    MAIN_API: str = GITHUB_API + "/repos/{owner}/{repo}"
    REPO_URL: str = GITHUB_API + "/users/{owner}/repos"
    SOURCE_URL: str = MAIN_API + "/contents/{path}?ref={branch}"
    TREE_URL: str = MAIN_API + "/git/trees/{branch}?recursive=1"

    MAIN_HEADERS: dict = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": "",
    }

    def __init__(
        self,
        owner: str,
        repo: str = "",
        branch: str = "main",
        token: str = "",
        headers: dict = None,
        include_empty_files: bool = False,
        verbose=False,
    ):
        # String Arguments
        self._owner = owner
        self._repo = repo
        self._branch = branch
        self._token = token

        # Boolean Arguments
        self._empty_files = include_empty_files
        self._verbose = verbose

        # Dict Arguments
        self._headers = headers or self.MAIN_HEADERS

        self._validate_args()

        if self._token and not self._headers.get("Authorization"):
            self.MAIN_HEADERS.update({"Authorization": self._token})

        super().__init__(headers=self._headers, json_format=True)

        self._repos = None
        self._repopaths = None
        self._repo_stats = None
        self._full_branch = None

    @classmethod
    def __call__(cls, *args, **kwargs):
        kwargs.update({"headers": cls.MAIN_HEADERS, "json_format": True})
        parent_parser = cls.__bases__[0]
        return parent_parser(*args, **kwargs)

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

        if not isinstance(self._headers, dict):
            raise GHException(
                f"The headers must be a dictionary, not {type(self._headers).__name__}."
            )

    def _get_repo_stats(self):
        api_parser = partial(self.main_parser, headers=self._headers)
        url = self.MAIN_API.format(owner=self._owner, repo=self._repo)
        main_stats = api_parser(url=url)

        if main_stats:
            stats = (
                (k, v)
                for k, v in main_stats.items()
                if k.endswith("count") or k == "description"
            )
        else:
            raise GHException(
                f"Unable to fetch repository statistics for "
                f"{self._owner + '/' + self._repo!r}."
            )

        other_endpoints = (
            "branches",
            "commits",
            "forks",
            "hooks",
            "issues",
            "keys",
            "milestones",
            "pulls",
            "releases",
            "stargazers",
            "tags",
            "actions/workflows",
            "community_profile",
            "discussions",
            "secret-scanning/alerts",
            "stats/code_frequency",
            "stats/commit_activity",
            "stats/contributors",
            "stats/participation",
            "traffic/clones",
            "traffic/views",
        )

        def _format_endpoint(endp):
            e = next((i for i in other_endpoints if i.endswith(endp)), "")
            return "-".join(Path(endp).parts[-2:]) if e else endp

        other_urls = (self.joinurl(url, i) for i in other_endpoints)
        other_exec = executor(lambda u: api_parser(url=u), other_urls)
        other_stats = zip(map(_format_endpoint, other_endpoints), other_exec)
        full_stats = chain.from_iterable((stats, other_stats))
        return _Repr(full_stats)

    def _main_gh_api(self) -> dict:
        url = self.REPO_URL.format(owner=self._owner)
        response = self.main_parser(url=url, headers=self._headers)
        if response:
            return response

    @verbose_wrap("Fetching main repository tree.")
    def _main_repotree(self) -> dict:
        url = self.TREE_URL.format(
            owner=self._owner, repo=self._repo, path="", branch=self._branch
        )
        response = self.main_parser(url=url, headers=self._headers)
        if response:
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
            return valid_p if not valid_p.startswith(".") else None

        if main_tree:
            tree = main_tree.get("tree")
            if tree is None:
                return
            repo_paths = tuple(k["path"] for k in tree if not_hidden(k["path"]))
        return repo_paths

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
    def main_parser(cls, *args, **kwargs):
        get_contents = kwargs.pop("get_contents", True)
        response = cls.__call__(*args, **kwargs)
        return [response, response.api_contents][get_contents]

    @classmethod
    def rate_limit(cls, key: str = None):
        url = cls.joinurl(cls.GITHUB_API, "rate_limit")
        response = cls.main_parser(url=url)

        if key is None:
            return response

        main_keys, inner_keys = map(
            lambda k: tuple(k.keys()), (response, next(iter(response.values())))
        )
        all_keys = tuple(chain.from_iterable((main_keys, inner_keys)))

        if key not in all_keys:
            raise GHException(
                f"The provided key {key!r} is not a valid option."
                f"\nAvailable keys are: {all_keys}"
            )

        if key in main_keys:
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
