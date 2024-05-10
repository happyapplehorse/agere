import pytest

from agere.utils.prompt_template import (
    PromptTemplateError,
    PromptTemplate,
    render_prompt,
    is_prompt_fully_filled,
    find_unfilled_variables,
)


@pytest.fixture
def prompt_template():
    return  """This is a test of a prompt template.
    The test name is {{ name }},
    and the number is {{ number }}.
    """

def test_render_prompt(prompt_template: str):
    # Action
    result = render_prompt(prompt_template=prompt_template, name="test_prompt_template", number=1, wrong_var="wrong")
    
    # Assert
    assert result == """This is a test of a prompt template.
    The test name is test_prompt_template,
    and the number is 1.
    """

def test_is_prompt_fully_filled(prompt_template: str):
    # Action
    partial_filled_prompt = render_prompt(prompt_template, name="test_is_prompt_fully_filled")
    fully_filled_prompt = render_prompt(partial_filled_prompt, number=2)
    
    # Assert
    assert is_prompt_fully_filled(prompt_template) is False
    assert is_prompt_fully_filled(partial_filled_prompt) is False
    assert is_prompt_fully_filled(fully_filled_prompt) is True

def test_find_unfilled_variables(prompt_template: str):
    # Assert
    assert find_unfilled_variables(prompt_template) == ["name", "number"]

    # Action
    partial_filled_prompt = render_prompt(prompt_template, name="test_find_unfilled_variables")
    
    # Assert
    assert find_unfilled_variables(partial_filled_prompt) == ["number"]
    
    # Action
    fully_filled_prompt = render_prompt(partial_filled_prompt, number=3)

    # Assert
    assert find_unfilled_variables(fully_filled_prompt) == []

def test_load_template(prompt_template: str):
    # Assert
    assert isinstance(PromptTemplate.load_template(prompt_template), PromptTemplate)

def test_prompt_template_render_method(prompt_template: str):
    # Setup
    template = PromptTemplate(prompt_template=prompt_template)

    # Action
    template = template.render(name="test_prompt_template_render_method").render(number=4)

    # Assert
    assert isinstance(template, PromptTemplate)
    assert template.prompt == """This is a test of a prompt template.
    The test name is test_prompt_template_render_method,
    and the number is 4.
    """

def test_prompt_template_prompt_method(prompt_template: str):
    # Setup
    template = PromptTemplate(prompt_template=prompt_template)

    # Action
    template = template.render(name="test_prompt_template_prompt_method")

    try:
        prompt = template.prompt
    except PromptTemplateError:
        prompt = "Error"

    # Assert
    assert prompt == "Error"
    assert str(template) == """This is a test of a prompt template.
    The test name is test_prompt_template_prompt_method,
    and the number is {{ number }}.
    """
    
    # Action
    template = template.render(number=5)

    try:
        prompt = template.prompt
    except PromptTemplateError:
        prompt = "Error"

    # Assert
    assert prompt == """This is a test of a prompt template.
    The test name is test_prompt_template_prompt_method,
    and the number is 5.
    """

def test_prompt_template_is_fully_filled_method(prompt_template: str):
    # Setup
    template = PromptTemplate(prompt_template=prompt_template)

    # Action
    template = template.render(name="test_prompt_template_is_fully_filled_method")
    
    # Assert
    assert template.is_fully_filled() is False
    
    # Action
    template = template.render(number=6)

    # Assert
    assert template.is_fully_filled() is True

def test_prompt_template_unfilled_variabels(prompt_template: str):
    # Setup
    template = PromptTemplate(prompt_template)

    # Assert
    assert template.unfilled_variables == ["name", "number"]

    # Action
    template.render(name="test_find_unfilled_variables")
    
    # Assert
    assert template.unfilled_variables == ["number"]
    
    # Action
    template.render(number=7)
    
    # Assert
    assert template.unfilled_variables == []
