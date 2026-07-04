"""
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
    m = re.search(r'([\u4e00-\u9fa5]{2,8})(?:的|今天|今日|明天|明日)?(?:天气|气温|温度|下雨|下雪|forecast|weather)', query)
    if m:
        return m.group(1)

    # 尝试匹配 "weather in XXX" 或 "forecast for XXX" 模式
    m = re.search(r'(?:weather|forecast|temperature)\s+(?:in|for|of)\s+(\S+)', query, re.IGNORECASE)
    if m:
        return m.group(1)

    # 尝试匹配 "XXX 的天气" 或 "XXX天气" 模式
    m = re.search(r'([\u4e00-\u9fa5a-zA-Z\s]{2,20})\s*(?:的|今天|今日|明天|明日)?\s*(?:天气|气温)', query)
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
            "113": "☀️ 晴", "116": "⛅ 多云", "119": "☁️ 阴",
            "122": "☁️ 阴天", "143": "🌫️ 雾", "176": "🌦️ 局部小雨",
            "200": "⛈️ 雷阵雨", "263": "🌦️ 阵雨",
            "266": "🌧️ 小雨", "296": "🌧️ 小雨", "299": "🌧️ 中雨",
            "302": "🌧️ 大雨", "305": "🌧️ 暴雨",
            "320": "🌨️ 中雪", "326": "🌨️ 小雪",
            "329": "❄️ 中雪", "332": "❄️ 大雪", "335": "❄️ 暴雪",
            "386": "⛈️ 雷阵雨", "389": "⛈️ 大雷雨",
        }
        weather_icon = icon_map.get(str(weather_code), "🌤️")

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
                "temp_max": f"{max_temp}°C",
                "temp_min": f"{min_temp}°C",
            })

        return {
            "city": f"{area_name}, {country}" if country else area_name,
            "description": description,
            "weather_icon": weather_icon,
            "current": {
                "temperature": f"{temp_c}°C",
                "feels_like": f"{feels_like}°C",
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
# Mock 天气数据库 (真实 API 不可用时兜底)
# ============================================================
MOCK_WEATHER_DB: Dict[str, Dict] = {
    "beijing": {
        "city": "Beijing, China",
        "description": "晴",
        "weather_icon": "☀️ 晴",
        "current": {
            "temperature": "32°C",
            "feels_like": "35°C",
            "humidity": "45%",
            "wind_speed": "12 km/h",
            "wind_direction": "NW",
            "visibility": "15 km",
            "uv_index": "7",
        },
        "forecast": [
            {"date": "(mock)", "description": "多云", "temp_min": "22°C", "temp_max": "33°C"},
            {"date": "(mock)", "description": "晴", "temp_min": "23°C", "temp_max": "35°C"},
            {"date": "(mock)", "description": "小雨", "temp_min": "20°C", "temp_max": "28°C"},
        ],
    },
    "shanghai": {
        "city": "Shanghai, China",
        "description": "多云",
        "weather_icon": "⛅ 多云",
        "current": {
            "temperature": "30°C",
            "feels_like": "33°C",
            "humidity": "70%",
            "wind_speed": "15 km/h",
            "wind_direction": "SE",
            "visibility": "12 km",
            "uv_index": "6",
        },
        "forecast": [
            {"date": "(mock)", "description": "小雨", "temp_min": "24°C", "temp_max": "31°C"},
            {"date": "(mock)", "description": "阴", "temp_min": "23°C", "temp_max": "29°C"},
            {"date": "(mock)", "description": "多云", "temp_min": "24°C", "temp_max": "32°C"},
        ],
    },
    "guangzhou": {
        "city": "Guangzhou, China",
        "description": "雷阵雨",
        "weather_icon": "⛈️ 雷阵雨",
        "current": {
            "temperature": "29°C",
            "feels_like": "32°C",
            "humidity": "85%",
            "wind_speed": "8 km/h",
            "wind_direction": "S",
            "visibility": "8 km",
            "uv_index": "4",
        },
        "forecast": [
            {"date": "(mock)", "description": "中雨", "temp_min": "24°C", "temp_max": "28°C"},
            {"date": "(mock)", "description": "多云", "temp_min": "25°C", "temp_max": "31°C"},
            {"date": "(mock)", "description": "晴", "temp_min": "26°C", "temp_max": "33°C"},
        ],
    },
    "default": {
        "city": "未知城市",
        "description": "晴",
        "weather_icon": "🌤️",
        "current": {
            "temperature": "25°C",
            "feels_like": "26°C",
            "humidity": "50%",
            "wind_speed": "10 km/h",
            "wind_direction": "N",
            "visibility": "10 km",
            "uv_index": "5",
        },
        "forecast": [
            {"date": "(mock)", "description": "多云", "temp_min": "20°C", "temp_max": "28°C"},
        ],
    },
}


def _fetch_weather_mock(city: str) -> Dict:
    """
    从 MOCK_WEATHER_DB 获取模拟天气数据
    优先匹配城市英文名/拼音,未匹配则返回默认数据
    """
    # 将中文城市名映射到拼音 key
    city_aliases = {
        "北京": "beijing", "beijing": "beijing",
        "上海": "shanghai", "shanghai": "shanghai",
        "广州": "guangzhou", "guangzhou": "guangzhou",
    }
    key = city_aliases.get(city.lower().strip(), city.lower().strip())
    return MOCK_WEATHER_DB.get(key, MOCK_WEATHER_DB["default"])


# ============================================================
# Mock 搜索数据库(非天气查询兜底)
# ============================================================
MOCK_SEARCH_DB: Dict[str, List[Dict[str, str]]] = {
    "python": [
        {"title": "Python 官方文档", "snippet": "Python 是一种解释型、面向对象的高级编程语言，支持多种编程范式。"},
        {"title": "Python 异步编程", "snippet": "asyncio 是 Python 3.4+ 引入的标准库，用于编写单线程并发代码。"},
        {"title": "Python 类型提示", "snippet": "Python 3.5+ 支持类型提示 (Type Hints)，可使用 typing 模块中的类型。"},
    ],
    "ai": [
        {"title": "人工智能简介", "snippet": "AI（人工智能）是计算机科学的一个分支，致力于创建能够模拟人类智能的系统。"},
        {"title": "大语言模型", "snippet": "LLM 是基于 Transformer 架构的大规模预训练语言模型，如 GPT、Claude 等。"},
        {"title": "RAG 技术", "snippet": "检索增强生成（RAG）将外部知识检索与 LLM 生成结合，提升回答准确性。"},
    ],
    "agent": [
        {"title": "AI Agent 概述", "snippet": "AI Agent 是能够自主感知环境、做出决策并执行行动的智能体系统。"},
        {"title": "Tool Use 模式", "snippet": "Agent 通过 Function Calling 机制调用外部工具，扩展自身能力边界。"},
        {"title": "ReAct 框架", "snippet": "ReAct (Reasoning + Acting) 让 LLM 交替进行推理和行动，完成复杂任务。"},
    ],
    "default": [
        {"title": "搜索结果", "snippet": "抱歉，未能找到完全匹配的结果，但这是相关的通用信息。"},
    ],
}


class SearchTool(BaseTool):
    """
    搜索工具:天气查询调用 wttr.in 真实 API,其余查询使用 Mock 兜底
    """

    name = "search"
    description = (
        "A search engine that finds information on various topics. "
        "Use this tool to search for facts, definitions, current information, etc. "
        "Provide relevant keywords as the query."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query keywords, e.g. 'Python async programming' or '北京天气'"
            }
        },
        "required": ["query"]
    }

    def execute(self, query: str = "", **kwargs) -> str:
        """执行搜索:天气走真实 API,其余走 Mock"""
        if not query.strip():
            return json.dumps(
                {"results": [], "message": "Empty query"}, ensure_ascii=False
            )

        query_stripped = query.strip()

        # ---- 天气查询: 走真实 wttr.in API ----
        if _is_weather_query(query_stripped):
            city = _extract_city(query_stripped)
            weather_data = _fetch_weather(city)

            # 真实 API 失败时,自动回退到 Mock 数据
            use_mock = "error" in weather_data
            if use_mock:
                weather_data = _fetch_weather_mock(city)

            output_lines = [
                "📍 " + weather_data["city"],
                weather_data["weather_icon"] + " " + weather_data["description"],
                "",
                "🌡️ 当前温度: " + weather_data["current"]["temperature"] + " (体感 " + weather_data["current"]["feels_like"] + ")",
                "💧 湿度: " + weather_data["current"]["humidity"],
                "💨 风速: " + weather_data["current"]["wind_speed"] + " " + weather_data["current"]["wind_direction"],
                "👁️ 能见度: " + weather_data["current"]["visibility"],
                "☀️ 紫外线指数: " + weather_data["current"]["uv_index"],
            ]

            if weather_data["forecast"]:
                output_lines.append("")
                output_lines.append("📅 未来预报:")
                for fc in weather_data["forecast"]:
                    output_lines.append("  " + fc["date"] + ": " + fc["description"] + " " + fc["temp_min"] + "~" + fc["temp_max"])

            result_text = "\n".join(output_lines)

            source = "mock (API unavailable)" if use_mock else "wttr.in (real-time)"
            return json.dumps(
                {
                    "query": query_stripped,
                    "city": weather_data["city"],
                    "source": source,
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
