"""
String utils.
"""

def strip_leading_whitespace(s: str) -> str:
    """For all lines in a string, strip the leading whitespace.
    Use when writing string configs as multi-line strings, which causes
    leading whitespace tabs in the string. This is for stripping out the
    whitespace.
    """
    lines = s.splitlines()
    stripped_lines = [ line.strip() for line in lines ] # strip whitespace

    # remove empty lines at beginning and end
    i_start = 0
    i_end = len(stripped_lines)
    for i, line in enumerate(stripped_lines):
        if line:
            i_start = i
            break
    for i, line in enumerate(reversed(stripped_lines)):
        if line:
            i_end = len(stripped_lines) - i
            break

    return "\n".join(stripped_lines[i_start:i_end])