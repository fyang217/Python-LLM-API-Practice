import json
import math
import os
import sys
from pathlib import Path
from statistics import mean

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, APIStatusError, OpenAI


def calculate_mean(numbers):
    return mean(numbers)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_mean",
            "description": "计算用户提供的一组数字的算术平均值。",
            "parameters": {
                "type": "object",
                "properties": {
                    "numbers": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 1,
                    }
                },
                "required": ["numbers"],
                "additionalProperties": False,
            },
        },
    }
]

THINKING_DISABLED = {"thinking": {"type": "disabled"}}


def execute_tool(name, raw_arguments, log):
    if name != "calculate_mean":
        return {"error": "未知工具。"}

    try:
        arguments = json.loads(raw_arguments)
    except (ValueError, RecursionError):
        return {"error": "工具参数不是有效的 JSON 对象。"}

    if not isinstance(arguments, dict) or arguments.keys() != {"numbers"}:
        return {"error": "参数必须是只包含 numbers 的对象。"}

    numbers = arguments["numbers"]
    if not isinstance(numbers, list) or not numbers:
        return {"error": "numbers 必须是非空列表。"}

    for number in numbers:
        if type(number) not in (int, float):
            return {"error": "列表元素必须是数字。"}
        if isinstance(number, float) and not math.isfinite(number):
            return {"error": "列表元素必须是有限数字。"}

    try:
        log("实际调用的函数：calculate_mean")
        log(f"传入 Python 函数的参数：numbers={numbers}")
        result = calculate_mean(numbers)
    except (OverflowError, ValueError):
        return {"error": "数字或计算结果超出可处理范围。"}
    log(f"Python 函数计算结果：{result}")
    return {"mean": result}


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("缺少 DEEPSEEK_API_KEY，请检查项目根目录下的 .env。", file=sys.stderr)
        return 1

    def log(message):
        print(message.replace(api_key, "[已隐藏]"), flush=True)

    prompt = input("请输入你的问题：")
    messages = [{"role": "user", "content": prompt}]

    try:
        with OpenAI(api_key=api_key, base_url="https://api.deepseek.com") as client:
            response = client.chat.completions.create(
                model="deepseek-flash",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                extra_body=THINKING_DISABLED,
            )

            if response.choices and response.choices[0].message.tool_calls:
                log("模型请求调用工具")
                message = response.choices[0].message
                messages.append(message.model_dump(exclude_none=True))
                for call in message.tool_calls:
                    result = execute_tool(call.function.name, call.function.arguments, log)
                    if "error" in result:
                        log(f"工具执行未成功：{result['error']}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                response = client.chat.completions.create(
                    model="deepseek-flash",
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="none",
                    extra_body=THINKING_DISABLED,
                )
                log("工具结果已返回模型")
            elif response.choices and response.choices[0].message.content:
                log("本次未调用工具，模型直接回答")
    except APIConnectionError:
        print("无法连接到 DeepSeek API，请检查网络连接。", file=sys.stderr)
        return 1
    except APIStatusError as error:
        print(f"DeepSeek API 请求失败（HTTP {error.status_code}）。", file=sys.stderr)
        return 1
    except APIError:
        print("DeepSeek API 请求失败。", file=sys.stderr)
        return 1

    if not response.choices or not response.choices[0].message.content:
        print("DeepSeek API 未返回文本回答。", file=sys.stderr)
        return 1

    answer = response.choices[0].message.content
    print(answer.replace(api_key, "[已隐藏]"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
