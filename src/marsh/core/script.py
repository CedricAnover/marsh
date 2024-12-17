import inspect
import ast
import re
import string
from abc import ABC, abstractmethod


class ScriptError(Exception):
    pass


class Script(ABC):
    def __init__(self, template_str: str):
        self.template: string.Template = string.Template(template_str)

    @abstractmethod
    def generate(self, *args, **kwargs) -> str:
        pass


class TemplateFactory:
    @staticmethod
    def create_bash_template(shebang: str = "#!/usr/bin/env bash", debugging: str = "set -eu -o pipefail") -> str:
        if not shebang.startswith("#!"):
            raise ValueError("Shebang must start with '#!'")
        template_string = "$shebang_\n\n$debugging_\n\n$statement_"
        return string.Template(template_string).safe_substitute(shebang_=shebang, debugging_=debugging)


class BashIfElifElseStatement(Script):
    def __init__(self):
        super().__init__("$if_part\n$elif_part\n$else_part\nfi")

        self._is_add_if_called = False
        self._is_add_elif_called = False
        self._is_add_else_called = False

        self._if_part: str | None = None
        self._elif_parts: list[str] = []
        self._else_part: str | None = None

    def add_if(self, condition: str, statement: str, use_double_brackets=False) -> None:
        if self._is_add_if_called:  # Check Flag if called already
            raise ScriptError("The 'if' can only be set once.")
        else:
            self._is_add_if_called = True

        if use_double_brackets:
            template_string = "if [[ $condition ]]\nthen\n\t$statement"
        else:
            template_string = "if [ $condition ]\nthen\n\t$statement"
        self._if_part = string.Template(template_string).safe_substitute(
            condition=condition,
            statement=statement
        )

    def add_elif(self, condition: str, statement: str, use_double_brackets=False) -> None:
        self._is_add_elif_called = True

        if use_double_brackets:
            template_string = "elif [[ $condition ]]\nthen\n\t$statement"
        else:
            template_string = "elif [ $condition ]\nthen\n\t$statement"
        elif_part = string.Template(template_string).safe_substitute(
            condition=condition,
            statement=statement
        )
        self._elif_parts.append(elif_part)

    def add_else(self, statement: str) -> None:
        if self._is_add_else_called:  # Check Flag if called already
            raise ScriptError("The 'if' can only be set once.")
        else:
            self._is_add_else_called = True
        template_string = "else\n\t$statement"
        self._else_part = string.Template(template_string).safe_substitute(statement=statement)

    def generate(self) -> str:
        if not self._is_add_if_called:
            raise ScriptError("The 'if' part is not set.")
        if self._is_add_elif_called and self._else_part is None:
            raise ScriptError("'else' part is not set.")

        out_statement = self.template.safe_substitute(if_part=self._if_part)

        if self._elif_parts:
            # Concatenate elif parts
            out_statement = string.Template(out_statement).safe_substitute(elif_part="\n".join(self._elif_parts))
        else:
            out_statement = string.Template(out_statement).safe_substitute(elif_part="")

        if self._else_part:
            out_statement = string.Template(out_statement).safe_substitute(else_part=self._else_part)
        else:
            out_statement = string.Template(out_statement).safe_substitute(else_part="")

        return out_statement


class BashCaseStatement(Script):
    def __init__(self):
        # Warn: The `$case_exression_name` still needs another `$` for reference!!!
        super().__init__(f"case $$case_exression_name in\n$cases\nesac")
        self._cases: list[str] = []

    def add_case(self, pattern: str, statement: str) -> None:
        template_string = "\t$pattern)\n\t\t$statement\n\t;;"
        case_ = string.Template(template_string).safe_substitute(
            pattern=pattern,
            statement=statement,
        )
        self._cases.append(case_)

    def generate(self, case_exression_name: str) -> str:
        if not self._cases:
            raise ScriptError("Cases cannot be empty.")

        return self.template.safe_substitute(
            case_exression_name=case_exression_name,
            cases="\n".join(self._cases)
        )


class BashExportEnvVarStatement(Script):
    def __init__(self, use_double_quotes: bool = True):
        if use_double_quotes:
            super().__init__('export $env_var_name="$value"')
        else:
            super().__init__("export $env_var_name='$value'")

    def generate(self, env_var_name: str, value: str) -> str:
        return self.template.safe_substitute(
            env_var_name=env_var_name.upper(),
            value=value
        )


class BashScript(Script):
    def __init__(self, shebang="#!/usr/bin/env bash", debugging="set -eu -o pipefail"):
        bash_template = TemplateFactory.create_bash_template(shebang=shebang, debugging=debugging)
        super().__init__(bash_template)

    def generate(self, statement: str) -> str:
        return self.template.safe_substitute(statement_=statement)

    def generate_from_statements(self, *statements: list[str], sep="\n\n") -> str:
        return self.generate(f"{sep}".join(statements))


__all__ = (
    "Script",
    "TemplateFactory",
    "BashScript",
    "BashIfElifElseStatement",
    "BashCaseStatement",
    "BashExportEnvVarStatement",
)
