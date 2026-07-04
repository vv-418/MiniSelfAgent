"""
Prompt 加载器 - 从 prompts/ 目录加载提示词模板文件

将提示词与代码解耦：
- 修改提示词只需编辑 .md 文件，无需改代码
- 支持模板变量替换（{variable} 格式）
- 文件缺失时回退到内置默认值，保证系统稳定
"""
import os
from typing import Optional

# prompts 目录路径（相对于项目根目录）
_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")


def _get_prompts_dir() -> str:
    """获取 prompts 目录的绝对路径"""
    return os.path.abspath(_PROMPTS_DIR)


def load_prompt(filename: str, fallback: str = "") -> str:
    """
    加载 prompts/ 目录下的提示词文件

    Args:
        filename: 文件名，如 "system_prompt.md"
        fallback: 文件不存在时的回退内容

    Returns:
        文件内容字符串，文件不存在时返回 fallback
    """
    filepath = os.path.join(_get_prompts_dir(), filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return fallback


def render_prompt(filename: str, variables: dict, fallback: str = "") -> str:
    """
    加载提示词模板并替换变量占位符

    模板中使用 {variable_name} 格式的占位符，
    调用时传入 variables={"variable_name": "value"} 进行替换。

    Args:
        filename: 模板文件名，如 "system_prompt.md"
        variables: 要替换的变量字典
        fallback: 文件不存在时的回退内容（支持变量替换）

    Returns:
        替换变量后的提示词字符串
    """
    template = load_prompt(filename, fallback=fallback)
    if not template:
        return template
    try:
        return template.format(**variables)
    except KeyError as e:
        # 模板中存在未提供的变量，保持原样返回
        return template
