"""Example plugin tools."""


def hello(name: str = "world") -> str:
    """Say hello to someone.

    Args:
        name: The name to greet. Defaults to "world".

    Returns:
        A greeting string.
    """
    return f"Hello, {name}! This is from the example plugin."


def add(a: float, b: float) -> float:
    """Add two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum.
    """
    return a + b
