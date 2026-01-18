"""Calculator tool for MCP server."""

from typing import Literal


def calculator(
    operation: Literal["add", "subtract", "multiply", "divide"],
    a: float,
    b: float
) -> dict:
    """
    Perform basic arithmetic operations.
    
    Args:
        operation: The arithmetic operation to perform
        a: First number
        b: Second number
        
    Returns:
        Dictionary with operation and result
    """
    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
    else:
        raise ValueError(f"Unknown operation: {operation}")
    
    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result
    }
