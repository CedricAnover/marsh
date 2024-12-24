from typing import Any
from abc import ABC, abstractmethod


class Script(ABC):
    """
    Abstract base class for generating scripts from templates. 
    Subclasses must implement the `generate` method to produce 
    a rendered script as a string.
    """

    def __init__(self, script_template: Any):
        """
        Initializes a Script instance with a template to be rendered.

        Args:
            `script_template` (Any): A template object (e.g., a `string.Template`, 
                                   a Jinja2 template, or a plain string) 
                                   that serves as the base for script generation.
        """
        self.script_template = script_template  # e.g. string.Template, Jinja2 Templates, or str

    @abstractmethod
    def generate(self, *args, **kwargs) -> str:
        """
        Abstract method to render the script template into a string.

        This method should be implemented in subclasses to provide specific logic
        for rendering the `script_template` using the provided arguments.

        Args:
            *args: Positional arguments to customize the script rendering.
            **kwargs: Keyword arguments to customize the script rendering.

        Returns:
            str: A string containing the rendered script, ready to be executed or used.
        """
        pass
