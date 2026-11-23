"""PowerShell entry point for the local pipeline or DeepSeek tool planner."""

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, APIStatusError, OpenAI

from agent.prompts import DEMO_TASK, SYSTEM_PROMPT
from agent.workflow import AnalysisRun, DESCRIPTIONS, TOOLS, run_workflow


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DEMO = DATA / "demo" / "demo_arg_data.xlsx"


def local_request():
    """Return a deterministic planner that advances only on successful results."""
    steps = iter(DESCRIPTIONS)

    def request(messages, tool_choice):
        if messages[-1]["role"] == "tool" and "error" in json.loads(messages[-1]["content"]):
            return {"content": "数据或前置步骤检查失败。"}
        name = next(steps, None) if tool_choice == "auto" else None
        if name is None:
            return {"content": "本地流程已结束。"}
        return {"tool_calls": [{
            "id": f"local_{name}",
            "type": "function",
            "function": {"name": name, "arguments": "{}"},
        }]}

    return request


def deepseek_request(client):
    """Adapt the OpenAI-compatible completion response to the workflow."""
    def request(messages, tool_choice):
        response = client.chat.completions.create(
            model="deepseek-flash", messages=messages, tools=TOOLS,
            tool_choice=tool_choice, extra_body={"thinking": {"type": "disabled"}},
        )
        if not response.choices:
            raise ValueError("DeepSeek 未返回可用消息。")
        return response.choices[0].message.model_dump(exclude_none=True)

    return request


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="科研 ARG 数据分析 Agent V1.0")
    parser.add_argument("mode", choices=("demo", "deepseek"), help="本地流程或 DeepSeek 多轮工具调用")
    parser.add_argument("--data", type=Path, default=DEMO, help="本地模式可指定 data/ 下的 Excel 或 CSV")
    parser.add_argument("--task", help="DeepSeek 任务。省略时可在终端输入，直接回车使用示例。")
    args = parser.parse_args()

    source = args.data.resolve()
    if not source.is_relative_to(DATA) or source.suffix.lower() not in {".xlsx", ".csv"} or not source.is_file():
        parser.error("请输入 data/ 下实际存在的 .xlsx 或 .csv 文件。")
    if args.mode == "deepseek" and source != DEMO:
        parser.error("DeepSeek 演示仅使用内置模拟 Excel；本地模式支持指定其他文件。")

    task = args.task or (input("请输入分析任务（回车使用示例）：").strip()
                         if args.mode == "deepseek" else DEMO_TASK)
    task = task or DEMO_TASK
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": task}]
    api_key = ""
    if args.mode == "deepseek":
        load_dotenv(ROOT / ".env")
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            print("缺少 DEEPSEEK_API_KEY。", file=sys.stderr)
            return 1

    output = ROOT / "outputs" / f"{args.mode}-{uuid4().hex[:10]}"
    output.mkdir(parents=True)
    run = AnalysisRun(source, output, source.is_relative_to(DATA / "demo"))
    print(f"本次输出目录：{output}", flush=True)
    try:
        if args.mode == "deepseek":
            with OpenAI(api_key=api_key, base_url="https://api.deepseek.com",
                        timeout=35.0, max_retries=0) as client:
                status = run_workflow(
                    deepseek_request(client), messages, run, require_report="报告" in task
                )
        else:
            status = run_workflow(local_request(), messages, run)
    except APIConnectionError:
        print("无法连接到 DeepSeek。", file=sys.stderr)
        return 1
    except APIStatusError as error:
        print(f"DeepSeek 请求失败（HTTP {error.status_code}）。", file=sys.stderr)
        return 1
    except (APIError, ValueError, OSError):
        print("流程执行失败。请检查 API 响应或已生成的工具日志。", file=sys.stderr)
        return 1
    finally:
        (output / "results.json").write_text(
            json.dumps(run.results, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
        )

    report = run.results.get("create_report")
    if report:
        for row in run.results["compare_dna_types"]["comparisons"]:
            difference = row["mean_difference_i_minus_e"]
            label = "缺少一组数据" if difference is None else f"{difference:.6g}"
            print(f"{row['region']} 的描述性均值差（iDNA − eDNA）：{label}")
        print(f"Word 报告：{output / report['report']}")
    else:
        print(f"本次未生成报告，已执行 {status['tool_calls']} 次工具调用。")
    return int(report is None)


if __name__ == "__main__":
    raise SystemExit(main())
