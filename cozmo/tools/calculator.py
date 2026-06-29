from . import register_tool

@register_tool()
def calculator(expression: str) -> str:
    """Evaluates a math expression. Input should be a valid Python math expression."""
    try:
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"
