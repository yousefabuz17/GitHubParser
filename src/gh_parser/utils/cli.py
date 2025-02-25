from argparse import ArgumentParser, ArgumentTypeError

from .type_hints import Iterable
from .utils import diff_set, get_parameters
from ..gh_parser import (
    get_metadata,
    get_parser,
    get_rate_limit,
    get_all_repos,
    get_all_repopaths,
    get_full_branch,
    get_path_contents,
    get_repo_stats,
    parse_url,
)


def cli_parser():
    arg_parser = ArgumentParser(description="")
    sub_parsers = arg_parser.add_subparsers(dest="command", help="All Command Options.")

    def _add_args(parser):
        def wrapper(*args, **kwargs):
            if all(("action" not in kwargs, all(s.startswith("--") for s in args))):
                kwargs["action"] = "store_true"
            else:
                kwargs["type"] = str
            return parser.add_argument(*args, **kwargs)

        return wrapper

    def _split_kwargs(cls, kwds: Iterable[str]):
        parser_kwargs = get_parameters(cls)
        try:
            fixed_kwds = dict((*k.split("="),) for k in kwds)
        except TypeError:
            raise ArgumentTypeError("'--kwargs' must be provided.")
        except ValueError:
            raise ArgumentTypeError(
                "Invalid key-value pair format." " Expected 'key=value'."
            )

        if _bad_kwds := diff_set(fixed_kwds, parser_kwargs):
            raise ArgumentTypeError(
                f"Invalid kwarg arguments: {_bad_kwds!r}"
                f"\nAvailable options: {parser_kwargs!r}"
            )

        return fixed_kwds

    main_args = _add_args(arg_parser)
    main_args("--version", help="Display the current version of 'gh_parser'.")
    main_args("--author", help="Display the author of 'gh_parser'.")
    main_args("--license", help="Display the license of 'gh_parser'.")
    main_args("--description", help="Display the description of 'gh_parser'.")
    main_args("--url", help="Display the GitHub URL of 'gh_parser'.")
    main_args("--verbose", help="Enable verbose output.")
    main_args("--metadata", help="Retrieve the full metadata contents of 'gh_parser'.")

    parseurl = sub_parsers.add_parser("parse-url", description="", help="")
    parser_kwargs = parseurl.add_argument("--kwargs", nargs="*")

    getrt_limit = sub_parsers.add_parser("rate-limit", description="", help="")
    getrt_args = _add_args(getrt_limit)
    getrt_args("-k", help="")

    repostats = sub_parsers.add_parser("repo-stats", description="", help="")
    repostats_kwargs = repostats.add_argument("--kwargs", nargs="*")

    repopaths = sub_parsers.add_parser("repo-paths", description="", help="")
    repopaths_kwargs = repopaths.add_argument("--kwargs", nargs="*")

    all_repos = sub_parsers.add_parser("all-repos", description="", help="")
    allrepos_kwargs = all_repos.add_argument("--kwargs", nargs="*")

    full_branch = sub_parsers.add_parser("full-branch", description="", help="")
    branch_kwargs = full_branch.add_argument("--kwargs", nargs="*")

    args = arg_parser.parse_args()
    metadata = get_metadata(enhance=False)
    main_arg_key = next(
        (k for k, v in vars(args).items() if v and k in (*metadata, "metadata")), None
    )

    if main_arg_key:
        return metadata.get(main_arg_key, metadata)

    command = args.command
    apiparser, gh_parser = map(get_parser, (0, 2))

    if command == "rate-limit":
        return get_rate_limit(key=args.k)
    
    command_mapping = (
        ("parse-url", parse_url),
        ("repo-stats", get_repo_stats),
        ("repo-paths", get_all_repopaths),
        ("all-repos", get_all_repos),
        ("full-branch", get_full_branch),
        ("path-contents", get_path_contents)
    )

    other_command = next((k for k in command_mapping if command in k), None)

    if other_command:
        command_key, command_function = other_command
        parser = apiparser if command_key == "parse-url" else gh_parser
        fixed_kwargs = _split_kwargs(parser, args.kwargs)
        return command_function(**fixed_kwargs)


if __name__ == "__main__":
    print(cli_parser())
