"""
计算器工具 - 支持基本数学运算
"""
import math
import re
from src.tools.base import BaseTool


class CalculatorTool(BaseTool):
    """
    Calculator - 安全地计算数学表达式
    
    支持: +, -, *, /, **, //, %, 以及常用数学函数
    """

    name = "calculator"
    description = (
        "A calculator that evaluates mathematical expressions. "
        "Use this tool to perform calculations. "
        "Examples: '2 + 3', '15 * 4', 'sqrt(144)', '2 ** 10', '(3 + 5) / 2'"
    )
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "The mathematical expression to evaluate, e.g. '2 + 3 * 4'"
            }
        },
        "required": ["expression"]
    }

    # 允许的安全函数白名单
    SAFE_FUNCTIONS = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "sqrt": math.sqrt,
        "pow": pow,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "pi": math.pi,
        "e": math.e,
        "ceil": math.ceil,
        "floor": math.floor,
    }

    def execute(self, expression: str = "", **kwargs) -> str:
        """
        安全地计算数学表达式
        """
        if not expression.strip():
            return "Error: Empty expression"

        # 清理表达式
        expr = expression.strip()

        # 安全校验：只允许数字、运算符、括号和白名单函数
        allowed_pattern = r'^[\d\s\+\-\*\/\%\.\(\)]+$|^[a-zA-Z_][\w\(\)\.\,\s]*$'
        if not re.match(allowed_pattern, expr):
            return f"Error: Expression contains disallowed characters: {expr}"

        try:
            # 使用受限的 eval 环境
            result = eval(expr, {"__builtins__": {}}, self.SAFE_FUNCTIONS)
            return f"{expr} = {result}"
        except ZeroDivisionError:
            return "Error: Division by zero"
        except Exception as e:
            return f"Error calculating '{expr}': {str(e)}"
