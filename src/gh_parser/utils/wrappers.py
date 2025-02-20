import time
from functools import wraps

from .type_hints import Any, Callable


VERBOSE_OUTPUTS = set()


def time_wrap(func: Callable):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        func_name = func.__name__
        if func_name == "full_branch":
            print(
                f"Please be advised that the execution time for the {func_name!r} method"
                " is dependent on the number of branches in the repository."
                "\nThis may take a while..."
            )
            time.sleep(1)

        start = time.perf_counter()
        f = func(self, *args, **kwargs)
        end = time.perf_counter()
        timer = end - start
        print(f"The execution time for {func_name!r} is {timer:.3f} seconds.")
        return f

    return wrapper


def verbose_wrap(voutput: str):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, "_verbose"):
                verbose = False
            else:
                verbose = self._verbose
            
            if verbose:
                if voutput not in VERBOSE_OUTPUTS:
                    VERBOSE_OUTPUTS.add(voutput)
                    print(voutput)

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def func_wrap(attr: str = "", cls_obj: Any=None):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ghp_cls = cls_obj(*args, **kwargs)
            return getattr(ghp_cls, attr)
        return wrapper
    return decorator