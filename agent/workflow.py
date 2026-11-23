"""Validated tools and bounded model/tool message exchange."""

import json
from pathlib import Path
from zipfile import BadZipFile

from arg_analysis_tools import calculate_arg_abundance, read_arg_excel
from tools.report_tools import create_report
from tools.statistics_tools import compare_dna_types
from tools.visualization_tools import create_figures


DESCRIPTIONS = {
    "read_arg_excel": "检查已授权 Excel 或 CSV 的 ARG 名称、样本分组及数据质量。",
    "calculate_arg_abundance": "计算每个样本的 ARG TPM 数值总和及按区域和 DNA 类型的描述性统计。",
    "compare_dna_types": "基于丰度结果计算总体和各区域 iDNA/eDNA 样本标准差和均值差。",
    "create_figures": "基于丰度和比较结果生成三张 PNG 图表。",
    "create_report": "基于数据质量、丰度、组间比较和图表生成 Word 报告。",
}
TOOLS = [
    {"type": "function", "function": {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    }}
    for name, description in DESCRIPTIONS.items()
]
MAX_TOOL_CALLS = 8


class AnalysisRun:
    """Manage results for one trusted input file and one new output directory."""

    def __init__(self, source, output, simulated, log=print):
        self.source = source
        self.output = output
        self.simulated = simulated
        self.log = log
        self.results = {}
        self.failed_steps = set()

    def dispatch(self, name, arguments):
        """Execute an explicitly registered step or return a structured error."""
        if name not in DESCRIPTIONS:
            return {"error": "未注册的工具。"}
        if arguments != {}:
            return {"error": "工具仅接受空参数对象，输入文件由启动命令指定。"}
        if name in self.results:
            return self.results[name]

        steps = {
            "read_arg_excel": lambda: read_arg_excel(self.source),
            "calculate_arg_abundance": lambda: calculate_arg_abundance(self.source),
            "compare_dna_types": lambda: compare_dna_types(self.results["calculate_arg_abundance"]),
            "create_figures": self._figures,
            "create_report": self._report,
        }
        try:
            result = steps[name]()
            if name in ("read_arg_excel", "calculate_arg_abundance"):
                result["file"] = self.source.name
            json.dumps(result, ensure_ascii=False, allow_nan=False)
        except KeyError:
            return {"error": "缺少前置工具结果，请先完成读取、计算或绘图。"}
        except (OSError, ValueError, OverflowError, BadZipFile):
            self.failed_steps.add(name)
            return {"error": "工具执行失败，请先运行数据质量检查并核对文件。"}
        self.results[name] = result
        return result

    def _figures(self):
        paths = create_figures(
            self.results["calculate_arg_abundance"], self.results["compare_dna_types"],
            self.output / "figures", self.simulated,
        )
        return {"figures": [path.relative_to(self.output).as_posix() for path in paths]}

    def _report(self):
        path = create_report(
            self.results["read_arg_excel"], self.results["calculate_arg_abundance"],
            self.results["compare_dna_types"],
            [self.output / path for path in self.results["create_figures"]["figures"]],
            self.output / "reports" / "arg_report.docx", self.simulated,
        )
        return {"report": path.relative_to(self.output).as_posix()}

    def event(self, index, name, arguments, result):
        """Write an audit event using only validated parameters and known fields."""
        event = {
            "call": index,
            "name": name if name in DESCRIPTIONS else "<unknown>",
            "arguments": {} if arguments == {} else "<rejected>",
            "result": (result if "error" in result else {
                "status": "ok",
                "arg_records": result.get("arg_record_count", result.get("data_rows")),
                "samples": result.get("sample_count"),
                "files": result.get("figures", [result["report"]] if "report" in result else []),
            }),
        }
        line = json.dumps(event, ensure_ascii=False, allow_nan=False)
        self.log(line)
        with (self.output / "tool_calls.jsonl").open("a", encoding="utf-8") as file:
            file.write(line + "\n")


def run_workflow(request_message, messages, run, max_calls=MAX_TOOL_CALLS, require_report=False):
    """Exchange assistant/tool messages while enforcing a per-task call budget."""
    used = 0
    seen_ids = set()
    prompted_steps = set()
    next_tool = None
    while True:
        choice = "auto" if used < max_calls else "none"
        if next_tool is not None:
            choice = {"type": "function", "function": {"name": next_tool}}
            next_tool = None
        message = request_message(messages, choice)
        calls = message.get("tool_calls") or []
        if not calls:
            pending = next((name for name in DESCRIPTIONS if name not in run.results), None)
            if (
                require_report and used < max_calls and pending
                and pending not in prompted_steps and pending not in run.failed_steps
            ):
                prompted_steps.add(pending)
                next_tool = pending
                messages.append({
                    "role": "user",
                    "content": f"报告任务还未完成。请调用 {pending}，根据工具实际返回的状态继续。",
                })
                run.log(f"模型提前结束，提醒继续执行 {pending}。")
                continue
            return {"tool_calls": used, "ended_with_text": bool(message.get("content"))}
        if used >= max_calls:
            return {"tool_calls": used, "ended_with_text": False}

        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        for call in calls:
            call_id = call["id"]
            function = call["function"]
            name = function["name"]
            try:
                arguments = json.loads(function["arguments"])
            except (ValueError, TypeError, RecursionError):
                arguments = None
            if call_id in seen_ids:
                raise ValueError("模型返回了重复的 tool_call_id。")
            seen_ids.add(call_id)
            if used < max_calls:
                used += 1
                result = run.dispatch(name, arguments)
                run.event(used, name, arguments, result)
            else:
                result = {"error": "已达到工具调用上限。"}
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps(result, ensure_ascii=False, allow_nan=False),
            })
