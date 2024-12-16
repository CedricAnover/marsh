import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class Result:
    stdout: bytes
    stderr: bytes

    def stdout_stder_to_dict(self, encoding="utf-8") -> dict[str, str]:
        # STDOUT and STDERR are converted to strings
        return {
            "stdout": self.stdout.decode(encoding),
            "stderr": self.stderr.decode(encoding)
        }

    def stdout_stderr_to_json(self, *args, encoding="utf-8", **kwargs) -> str:
        return json.dumps(self.stdout_stder_to_dict(encoding=encoding), *args, **kwargs)


class IResultIO(ABC):
    @abstractmethod
    def read_results(self,
                     *args,
                     encoding="utf-8",
                     **kwargs
                     ) -> Any:
        pass

    @abstractmethod
    def write_result(self,
                     result: Result,
                     file_path: str,
                     *args,
                     encoding: str = "utf-8",
                     **kwargs
                     ) -> None:
        pass
