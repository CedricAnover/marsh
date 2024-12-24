import string

from marsh.exceptions import ScriptError
from marsh import Script


_BASH_SCRIPT_TEMPLATE = r"""$shebang_

$debugging_

$statements_

"""


class BashScript(Script):
    """
    An implementation of the `Script` ABC for generating Bash scripts from templates.

    This class provides a way to construct Bash scripts by specifying a shebang, 
    debugging settings, and script statements. The resulting script can be rendered 
    as a string using the `generate` method.
    """
    def __init__(self,
                 shebang: str = "#!/usr/bin/env bash",
                 debugging: str = "set -eu -o pipefail"
                 ):
        """
        Initializes a `BashScript` instance with a default shebang and debugging options.

        Args:
            `shebang` (str): The shebang line to specify the shell for the script. 
                           Defaults to `#!/usr/bin/env bash`.
            `debugging` (str): Debugging options to set shell behavior. Defaults to 
                             `set -eu -o pipefail`.

        Raises:
            ScriptError: If the provided `shebang` does not start with `#!`.
        """

        # Make sure that shebang starts with `#!`.
        if not shebang.startswith("#!"):
            raise ScriptError("Shebang must start with '#!'.")

        template = string.Template(_BASH_SCRIPT_TEMPLATE)
        template_str = template.safe_substitute(
            shebang_=shebang,
            debugging_=debugging
        )
        super().__init__(template_str)

    def generate(self,
                 *statements: list[str],
                 sep: str = "\n"
                 ) -> str:
        """
        Renders the Bash script by substituting the provided script statements 
        into the template.

        Args:
            `*statements` (list[str]): A list of Bash statements to include in the script.
            `sep` (str): Separator for joining multiple statements. Defaults to `\\n`.

        Returns:
            str: A string containing the rendered Bash script.
        """

        statements_ = f"{sep}".join(statements)
        return string.Template(self.script_template).safe_substitute(
            statements_=statements_
        ).rstrip()
