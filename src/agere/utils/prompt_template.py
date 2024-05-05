"""
This module provides utilities for managing and rendering string templates that use double braces `{{}}` 
to denote placeholders for variables. It includes a `PromptTemplate` class for creating, managing, 
and rendering these templates, along with functions to check if a template is fully filled and to 
perform the rendering.

Templates are strings that use double curly braces to enclose variable names, e.g., `{{variable}}`,
which can be dynamically replaced with actual values.

Classes:
    PromptTemplate: Encapsulates template management and rendering.

Exceptions:
    PromptTemplateError: Custom exception for handling template errors.

Functions:
    render_prompt(prompt_template: str, **variables) -> str: Renders a template with variables.
    is_prompt_fully_filled(prompt: str) -> bool: Checks if a template has unfilled placeholders.
"""


from __future__ import annotations
import re
from typing import Self

from ._exceptions import AgereUtilsError


class PromptTemplateError(AgereUtilsError):
    """Raised when encountering an error related to the prompt template."""


class PromptTemplate:
    """A class for managing and rendering templates with placeholders.

    These templates are strings that use double curly braces `{{}}` to denote variable names,
    which are intended to be replaced by actual values when the template is rendered.
    Example of a template: "Hello, {{ name }}!"

    Attributes:
        prompt_template (str): The current state of the template string, initially set with placeholders.

    Methods:
        load_template(prompt_template: str) -> PromptTemplate:
            Class method to create a new instance with the specified template.
        render(**variables) -> Self:
            Renders the template with provided variables and updates the instance.
            This method replaces placeholders in the format `{{ variable }}` with values from `variables`.
        prompt() -> str:
            Returns the fully filled template or raises an error if unfilled placeholders remain.
            This method is used to retrieve the final rendered string if it is fully filled.
        is_fully_filled() -> bool:
            Checks if the template has any unfilled placeholders. This method determines whether all
            placeholders have been replaced.
    """

    def __init__(self, prompt_template: str):
        """
        Initializes a new instance of PromptTemplate with a prompt template string.

        Args:
            prompt_template (str): The initial template string with placeholders.
        """
        self.prompt_template = prompt_template

    @classmethod
    def load_template(cls, prompt_template: str) -> PromptTemplate:
        """
        Class method to create a new instance of PromptTemplate from a given template string.

        Args:
            prompt_template (str): The template string to initialize the template.

        Returns:
            PromptTemplate: A new instance of PromptTemplate initialized with the specified template.
        """
        return PromptTemplate(prompt_template)

    def render(self, **variables) -> Self:
        """
        Renders the template with provided variables and updates the instance. This method replaces
        placeholders in the format `{{ variable }}` with values from `variables`. It allows for chainable 
        method calls, enabling a fluent interface pattern.

        Args:
            **variables:
                Arbitrary keyword arguments where the key is the placeholder variable name and 
                the value is the replacement value.

        Returns:
            PromptTemplate: The instance itself with updated template, allowing for method chaining.

        Example of usage:
            template = PromptTemplate("Hello, {{ name }}! Today is {{ day }}.")
            template.render(name="Alice").render(day="Wednesday")
        """
        prompt_template = render_prompt(self.prompt_template, **variables)
        self.prompt_template = prompt_template
        return self

    @property
    def prompt(self) -> str:
        """
        Returns the fully filled template if all placeholders have been replaced, otherwise raises an error.

        Returns:
            str: The fully filled template string.

        Raises:
            PromptTemplateError: If the template contains unfilled placeholders.
        """
        if not self.is_fully_filled():
            raise PromptTemplateError("The prompt template is not fully filled.")
        return self.prompt_template

    def is_fully_filled(self) -> bool:
        """
        Checks if the template has any unfilled placeholders remaining.

        Returns:
            bool: True if no placeholders remain unfilled, False otherwise.
        """
        return is_prompt_fully_filled(self.prompt_template)

    def __str__(self) -> str:
        """
        Returns the string representation of the current template, which may or may not be fully filled.

        Returns:
            str: The current state of the template string.
        """
        return self.prompt_template
    

def render_prompt(prompt_template: str, **variables) -> str:
    """
    Renders a template string by replacing placeholders formatted as `{{ variable }}`
    with values provided in the variables keyword arguments.

    Args:
        prompt_template (str): The template string containing placeholders.
        **variables:
            Arbitrary keyword arguments where the key is the placeholder variable
            name and the value is the replacement value.

    Returns:
        str: The template string with placeholders replaced by actual values.
    """
    pattern = re.compile(r"\{\{\s*(\w+)\s*\}\}")

    def replace_func(match):
        key = match.group(1)
        return str(variables.get(key, match.group(0)))

    prompt = pattern.sub(replace_func, prompt_template)

    return prompt
    
def is_prompt_fully_filled(prompt: str) -> bool:
    """
    Checks if a template string contains any unfilled placeholders.

    Args:
        prompt (str): The template string to check.

    Returns:
        bool: True if no unfilled placeholders are found, False otherwise.
    """
    pattern = re.compile(r"\{\{\s*\w+\s*\}\}")
    unreplaced_variables = pattern.findall(prompt)
    
    if unreplaced_variables:
        return False
    else:
        return True
