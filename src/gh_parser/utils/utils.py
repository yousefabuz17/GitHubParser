import base64
import inspect
import operator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from .type_hints import Any, Callable, Generator, Union


class _Repr(dict):
    """
    A custom dictionary class that overrides the `__repr__` method.

    ### Methods:
        - `_format_value`: Format the string object.
        - `__repr__`: Return the string representation of the dictionary.

    ### Usage:
        ```python
        r = _Repr({"a": 1, "b": {"c": 2, "d": 3}})
        print(r)

        # Output:
        {'a': <int>, 'b': {'c': <int>, 'd': <int>}}
        ```
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _format_value(self, str_obj) -> str:
        return f"<{type(str_obj).__name__}>"

    def __repr__(self) -> str:
        return f"""{
            {
                k: {
                    m: self._format_value(n)
                    for m, n in v.items()
                }
                if isinstance(v, dict)
                else self._format_value(v)
                for k, v in self.items()
            }
        }"""


def get_parameters(obj: Any, keys_only: bool = True) -> Union[dict, tuple[str]]:
    params = {k: v.default for k, v in inspect.signature(obj).parameters.items()}
    return [params, tuple(params.keys())][keys_only]


def str_instance(obj: Any) -> bool:
    return isinstance(obj, str)


def decode_string(str_obj) -> str:
    return base64.b64decode(str_obj).decode("utf-8")


def executor(func: Callable = None, *args, **kwargs) -> Union[Any, Generator]:
    executor_type = kwargs.pop("executor_type", "tpe")
    executor_only = kwargs.pop("executor_only", False)
    cls_exec = [ProcessPoolExecutor, ThreadPoolExecutor][executor_type == "tpe"]
    exec_kwargs = get_parameters(cls_exec, keys_only=False)
    main_kwargs = {k: kwargs.pop(k, v) for k, v in exec_kwargs.items()}
    new_executor = cls_exec(**main_kwargs)

    if executor_only:
        return new_executor
    return yield_executor(cls_exec(**main_kwargs).map(func, *args, **kwargs))


def yield_executor(__executor) -> Generator:
    yield from __executor


def diff_set(*args):
    return operator.sub(*map(set, args))
