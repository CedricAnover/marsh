import inspect
import ast
import re
import string
from abc import ABC, abstractmethod


class ScriptStatement(ABC):
    @abstractmethod
    def exec(self, *args, **kwargs) -> None:
        pass


class ScriptExpression:
    ...


class Script:
    # Properties:
    # -----------
    # template: string.Template | str
    # shebang: str = "#!/usr/bin/env bash"
    # statements: list[str] = []
    # debugging: str | list[str] = "set -eu -o pipefail"
    # stmt_sep: str = "\n\n"
    # ...
    # ...

    # Methods:
    # --------
    # render(*args, **kwargs) -> str
    # ...
    # ...
    # ...
    ...
