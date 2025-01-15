import sys
from io import StringIO

from marsh.utils.output_streams import suppress_output, mask_sensitive_data


def test_suppress_output():
    # Create a new StringIO object to capture the output
    captured_output = StringIO()
    sys.stdout = captured_output  # Redirect sys.stdout to the StringIO object

    with suppress_output():
        print("This will be suppressed")

    # After the context manager, the output should be suppressed
    assert captured_output.getvalue() == ''

    # Reset sys.stdout to its original value
    sys.stdout = sys.__stdout__


def test_suppress_output_restoration():
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    with suppress_output():
        pass

    # Check if stdout and stderr are restored
    assert sys.stdout is old_stdout
    assert sys.stderr is old_stderr


def test_mask_sensitive_data_single_pattern():
    text = "My password is 12345"
    patterns = [r'\d+']  # pattern to match digits
    result = mask_sensitive_data(text, patterns)
    assert result == "My password is ***"


def test_mask_sensitive_data_default_placeholder():
    text = "My password is 12345"
    patterns = [r'\d+']
    result = mask_sensitive_data(text, patterns)
    assert result == "My password is ***"


def test_mask_sensitive_data_custom_placeholder():
    text = "My password is 12345"
    patterns = [r'\d+']
    result = mask_sensitive_data(text, patterns, placeholder="####")
    assert result == "My password is ####"


def test_mask_sensitive_data_multiple_patterns():
    text = "My email is test@example.com and my phone is 9876543210"
    patterns = [r'\d+', r'\S+@\S+\.\S+']  # match digits and email
    result = mask_sensitive_data(text, patterns)
    assert result == "My email is *** and my phone is ***"


def test_mask_sensitive_data_no_matches():
    text = "No sensitive data here!"
    patterns = [r'\d+', r'\S+@\S+\.\S+']
    result = mask_sensitive_data(text, patterns)
    assert result == text  # No sensitive data, so it should remain unchanged


def test_mask_sensitive_data_no_patterns():
    text = "Sensitive data is safe."
    result = mask_sensitive_data(text, [])
    assert result == text  # No patterns to mask, text should remain unchanged
