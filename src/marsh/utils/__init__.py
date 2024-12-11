import warnings
from functools import wraps


def deprecated(message: str = ""):
    def outer(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(
                message if message else f"{func.__name__} is deprecated and will be removed in a future version. Please use an alternative.",
                DeprecationWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)
        return wrapper
    return outer
