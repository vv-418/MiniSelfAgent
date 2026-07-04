"""Script to write the new search.py with weather API support"""
import os

TARGET = r"d:\python_project\my_project\MiniSelfAgent\src\tools\search.py"

content = '''"""
搜索工具 - 真实天气 API (wttr.in) + Mock 兜底
天气查询走真实 API,其余查询保留 Mock 兜底
"""
import json
import re
from typing import Dict, List
from src.tools.base import BaseTool

try:
    import requests
except ImportError:
    requests = None

import config


# 天气相关关键词
WEATHER_KEYWORDS = [
    "天气", "气温", "温度", "下雨", "下雪", "晴", "阴", "多云",
    "weather", "forecast", "rain", "snow", "sunny", "cloudy",
    "风力", "湿度", "紫外线", "空气质量",
]


def _is_weather_query(query: str) -> bool:
    """判断查询是否为天气相关"""
    query_lower = query.lower()
    return any(kw in query_lower for kw in WEATHER_KEYWORDS)


def _extract_city(query: str) -> str:
    """
    从查询中提取城市名
    支持格式: "北京天气", "北京 的天气", "weather in Beijing", "Beijing weather"
    """
    # 尝试匹配 "XXX天气/天气预报/天气如何" 模式
    m = re.search(
        r"([\\u4e00-\\u9fa5]{2,8})(?:的|今天|今日|明天|明日)?(?:天气|气温|温度|下雨|下雪|forecast|weather)",
        query,
    )
    if m:
        return m.group(1)

    # 尝试匹配 "weather in XXX" 或 "forecast for XXX" 模式
    m = re.search(
        r"(?:weather|forecast|temperature)\\s+(?:in|for|of)\\s+(\\S+)",
        query,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)

    # 尝试匹配 "XXX 的天气" 或 "XXX天气" 模式
    m = re.search(
        r"([\\u4e00-\\u9fa5a-zA-Z\\s]{2,20})\\s*(?:的|今天|今日|明天|明日)?\\s*(?:天气|气温)",
        query,
    )
    if m:
        return m.group(1).strip()

    # 默认返回配置中的默认城市
    return config.WEATHER_DEFAULT_CITY


def _fetch_weather(city: str) -> Dict:
    """
    从 wttr.in 获取真实天气数据
    返回解析后的天气信息字典
    """
    if requests is None:
        return {"error": "requests 库未安装,请运行: pip install requests"}

    url = f"{config.WEATHER_API_URL}/{city}"
    params = {"format": "j1"}  # JSON 格式

    try:
        resp = requests.get(url, params=params, timeout=config.WEATHER_API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        return {"error": f"天气 API 请求超时 ({config.WEATHER_API_TIMEOUT}s)"}
    except requests.exceptions.ConnectionError:
        return {"error": "无法连接到天气 API (wttr.in),请检查网络"}
    except requests.exceptions.HTTPError as e:
        return {"error": f"天气 API 返回错误: {e}"}
    except (ValueError, KeyError) as e:
        return {"error": f"天气数据解析失败: {e}"}

    # 解析天气数据
    try:
        current = data["current_condition"][0]
        nearest = data["nearest_area"][0]

        # 城市名
        area_name = nearest.get("areaName", [{}])[0].get("value", city)
        country = nearest.get("country", [{}])[0].get("value", "")

        # 当前天气
        temp_c = current.get("temp_C", "?")
        feels_like = current.get("FeelsLikeC", "?")
        humidity = current.get("humidity", "?")
        wind_speed = current.get("windspeedKmph", "?")
        wind_dir = current.get("winddir16Point", "")
        visibility = current.get("visibility", "?")
        uv_index = current.get("uvIndex", "?")

        # 天气描述(中文)
        desc_list = current.get("lang_zh", [])
        if desc_list:
            description = desc_list[0].get("value", "")
        else:
            desc_list = current.get("weatherDesc", [])
            description = desc_list[0].get("value", "") if desc_list else ""

        # 天气图标映射
        weather_code = current.get("weatherCode", "")
        icon_map = {
            "113": "\u2600\ufe0f \u6674",
            "116": "\u26c5 \u591a\u4e91",
            "119": "\u2601\ufe0f \u9634",
            "122": "\u2601\ufe0f \u9634\u5929",
            "143": "\ud83c\udf2b\ufe0f \u96fe",
            "176": "\ud83c\udf26\ufe0f \u5c40\u90e8\u5c0f\u96e8",
            "200": "\u26c8\ufe0f \u96f7\u9635\u96e8",
            "263": "\ud83c\udf26\ufe0f \u9635\u96e8",
            "266": "\ud83c\udf27\ufe0f \u5c0f\u96e8",
            "296": "\ud83c\udf27\ufe0f \u5c0f\u96e8",
            "299": "\ud83c\udf27\ufe0f \u4e2d\u96e8",
            "302": "\ud83c\udf27\ufe0f \u5927\u96e8",
            "305": "\ud83c\udf27\ufe0f \u66b4\u96e8",
            "320": "\ud83c\udf28\ufe0f \u4e2d\u96ea",
            "326": "\ud83c\udf28\ufe0f \u5c0f\u96ea",
            "329": "\u2744\ufe0f \u4e2d\u96ea",
            "332": "\u2744\ufe0f \u5927\u96ea",
            "335": "\u2744\ufe0f \u66b4\u96ea",
            "386": "\u26c8\ufe0f \u96f7\u9635\u96e8",
            "389": "\u26c8\ufe0f \u5927\u96f7\u96e8",
        }
        weather_icon = icon_map.get(str(weather_code), "\ud83c\udf24\ufe0f")

        # 未来三天预报
        forecasts = []
        for day in data.get("weather", [])[:3]:
            date = day.get("date", "")
            max_temp = day.get("maxtempC", "?")
            min_temp = day.get("mintempC", "?")
            hourly = day.get("hourly", [])
            if hourly:
                mid_day = hourly[4] if len(hourly) > 4 else hourly[0]
                day_desc_list = mid_day.get("lang_zh", [])
                if day_desc_list:
                    day_desc = day_desc_list[0].get("value", "")
                else:
                    day_desc_list = mid_day.get("weatherDesc", [])
                    day_desc = day_desc_list[0].get("value", "") if day_desc_list else ""
            else:
                day_desc = ""
            forecasts.append({
                "date": date,
                "description": day_desc,
                "temp_max": f"{max_temp}\\u00b0C",
                "temp_min": f"{min_temp}\\u00b0C",
            })

        return {
            "city": f"{area_name}, {country}" if country else area_name,
            "description": description,
            "weather_icon": weather_icon,
            "current": {
                "temperature": f"{temp_c}\\u00b0C",
                "feels_like": f"{feels_like}\\u00b0C",
                "humidity": f"{humidity}%",
                "wind_speed": f"{wind_speed} km/h",
                "wind_direction": wind_dir,
                "visibility": f"{visibility} km",
                "uv_index": uv_index,
            },
            "forecast": forecasts,
        }
    except (KeyError, IndexError) as e:
        return {"error": f"天气数据字段缺失: {e}"}


# ============================================================
# Mock 搜索数据库 (非天气查询兜底)
# ============================================================
MOCK_SEARCH_DB: Dict[str, List[Dict[str, str]]] = {
    "python": [
        {"title": "Python 官方文档", "snippet": "Python 是一种解释型、面向对象的高级编程语言,支持多种编程范式。"},
        {"title": "Python 异步编程", "snippet": "asyncio 是 Python 3.4+ 引入的标准库,用于编写单线程并发代码。"},
        {"title": "Python 类型提示", "snippet": "Python 3.5+ 支持类型提示 (Type Hints),可使用 typing 模块中的类型。"},
    ],
    "ai": [
        {"title": "人工智能简介", "snippet": "AI(人工智能)是计算机科学的一个分支,致力于创建能够模拟人类智能的系统。"},
        {"title": "大语言模型", "snippet": "LLM 是基于 Transformer 架构的大规模预训练语言模型,如 GPT、Claude 等。"},
        {"title": "RAG 技术", "snippet": "检索增强生成(RAG)将外部知识检索与 LLM 生成结合,提升回答准确性。"},
    ],
    "agent": [
        {"title": "AI Agent 概述", "snippet": "AI Agent 是能够自主感知环境、做出决策并执行行动的智能体系统。"},
        {"title": "Tool Use 模式", "snippet": "Agent 通过 Function Calling 机制调用外部工具,扩展自身能力边界。"},
        {"title": "ReAct 框架", "snippet": "ReAct (Reasoning + Acting) 让 LLM 交替进行推理和行动,完成复杂任务。"},
    ],
    "default": [
        {"title": "搜索结果", "snippet": "抱歉,未能找到完全匹配的结果,但这是相关的通用信息。"},
    ],
}


class SearchTool(BaseTool):
    """
    搜索工具: 天气查询调用 wttr.in 真实 API,其余查询使用 Mock 兜底
    """

    name = "search"
    description = (
        "Search tool. Weather queries (containing keywords like \\u5929\\u6c14/weather/temperature) "
        "fetch real-time data from wttr.in. Other queries return mock search results."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search query keywords. "
                    "For weather, provide city name, e.g. \\u5317\\u4eac\\u5929\\u6c14 or weather in Tokyo. "
                    "For other topics, provide relevant keywords."
                ),
            }
        },
        "required": ["query"],
    }

    def execute(self, query: str = "", **kwargs) -> str:
        """执行搜索: 天气走真实 API,其余走 Mock"""
        if not query.strip():
            return json.dumps(
                {"results": [], "message": "Empty query"}, ensure_ascii=False
            )

        query_stripped = query.strip()

        # ---- 天气查询: 走真实 wttr.in API ----
        if _is_weather_query(query_stripped):
            city = _extract_city(query_stripped)
            weather_data = _fetch_weather(city)

            if "error" in weather_data:
                return json.dumps(
                    {"query": query_stripped, "error": weather_data["error"]},
                    ensure_ascii=False,
                    indent=2,
                )

            # 格式化输出
            output_lines = [
                "\\U0001f4cd " + weather_data["city"],
                weather_data["weather_icon"] + " " + weather_data["description"],
                "",
                "\\U0001f321\\ufe0f  \\u5f53\\u524d\\u6e29\\u5ea6: "
                + weather_data["current"]["temperature"]
                + " (\\u4f53\\u611f "
                + weather_data["current"]["feels_like"]
                + ")",
                "\\U0001f4a7 \\u6e7f\\u5ea6: " + weather_data["current"]["humidity"],
                "\\U0001f4a8 \\u98ce\\u901f: "
                + weather_data["current"]["wind_speed"]
                + " "
                + weather_data["current"]["wind_direction"],
                "\\U0001f441\\ufe0f  \\u80fd\\u89c1\\u5ea6: " + weather_data["current"]["visibility"],
                "\\u2600\\ufe0f  \\u7d2b\\u5916\\u7ebf\\u6307\\u6570: " + weather_data["current"]["uv_index"],
            ]

            if weather_data["forecast"]:
                output_lines.append("")
                output_lines.append("\\U0001f4c5 \\u672a\\u6765\\u9884\\u62a5:")
                for fc in weather_data["forecast"]:
                    output_lines.append(
                        "  "
                        + fc["date"]
                        + ": "
                        + fc["description"]
                        + " "
                        + fc["temp_min"]
                        + "~"
                        + fc["temp_max"]
                    )

            result_text = "\\n".join(output_lines)

            return json.dumps(
                {
                    "query": query_stripped,
                    "city": weather_data["city"],
                    "source": "wttr.in (real-time)",
                    "result": result_text,
                },
                ensure_ascii=False,
                indent=2,
            )

        # ---- 非天气查询: Mock 兜底 ----
        query_lower = query_stripped.lower()
        matched_results: List[Dict[str, str]] = []
        for keyword, results in MOCK_SEARCH_DB.items():
            if keyword in query_lower or any(
                kw in query_lower for kw in keyword.split()
            ):
                matched_results.extend(results)

        if not matched_results:
            matched_results = MOCK_SEARCH_DB["default"]

        top_results = matched_results[:3]
        output = {
            "query": query_stripped,
            "source": "mock",
            "results": top_results,
            "total_found": len(matched_results),
        }
        return json.dumps(output, ensure_ascii=False, indent=2)
'''

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Written {len(content)} bytes to {TARGET}")
