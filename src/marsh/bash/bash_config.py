from dataclasses import dataclass, field
import os


@dataclass
class BashGrammarConfig:
    bash_path: str = "bash"
    bash_options: list[str] = field(default_factory=lambda: ["-c"])


@dataclass
class BashScriptConfig:
    shebang: str = "#!/usr/bin/env bash"
    sep: str = "\n\n"
    strict_mode: str = "set -eu -o pipefail"


@dataclass
class BashConfig:
    bash_grammar: BashGrammarConfig = field(default_factory=lambda: BashGrammarConfig())
    bash_script: BashScriptConfig = field(default_factory=lambda: BashScriptConfig())
    env: dict = field(default_factory=dict)
    cwd: str = os.getcwd()
