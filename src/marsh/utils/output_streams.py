import re
import sys
from contextlib import contextmanager
from io import StringIO


@contextmanager
def suppress_output():
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = StringIO(), StringIO()
    try:
        yield
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


def mask_sensitive_data(text: str, patterns: list[str], placeholder="***") -> str:
    """Masks sensitive data in the given text based on provided regex patterns."""
    for pattern in patterns:
        text = re.sub(pattern, placeholder, text)
    return text
