import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock

from agent.agent import deepseek_request, local_request
from agent.workflow import AnalysisRun, run_workflow
from tests.fixtures import DATA, DEMO


def call(name, call_id, arguments="{}"):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


class WorkflowTests(unittest.TestCase):
    def test_model_receives_correct_tool_ids_and_can_recover(self):
        with TemporaryDirectory() as folder:
            run = AnalysisRun(DEMO, Path(folder), True, log=lambda _: None)

            def model(messages, choice):
                self.assertEqual(choice, "auto")
                previous = messages[-1]
                if previous["role"] == "user":
                    return {"tool_calls": [call("read_arg_excel", "a", '{"path":"../secret.xlsx"}')]}
                result = json.loads(previous["content"])
                if previous["tool_call_id"] == "a":
                    self.assertIn("error", result)
                    return {"tool_calls": [call("read_arg_excel", "b")]}
                if previous["tool_call_id"] == "b":
                    self.assertEqual(result["sample_count"], 16)
                    return {"tool_calls": [call("calculate_arg_abundance", "c")]}
                self.assertEqual(previous["tool_call_id"], "c")
                self.assertEqual(result["samples"][0]["arg_tpm_sum"], 10)
                return {"content": "done"}

            status = run_workflow(model, [{"role": "user", "content": "demo"}], run)
            self.assertEqual(status["tool_calls"], 3)
            events = [json.loads(line) for line in (Path(folder) / "tool_calls.jsonl").read_text(
                encoding="utf-8").splitlines()]
            self.assertEqual([event["arguments"] for event in events], ["<rejected>", {}, {}])
            self.assertEqual(events[1]["name"], "read_arg_excel")

    def test_cap_and_malformed_parameters(self):
        with TemporaryDirectory() as folder:
            run = AnalysisRun(DEMO, Path(folder), True, log=lambda _: None)

            def model(messages, choice):
                if choice == "auto":
                    return {"tool_calls": [
                        call("read_arg_excel", "a", "{"),
                        call("create_report", "b"),
                    ]}
                tool_messages = messages[-2:]
                self.assertEqual([entry["tool_call_id"] for entry in tool_messages], ["a", "b"])
                self.assertTrue(all("error" in json.loads(entry["content"]) for entry in tool_messages))
                return {"content": "done"}

            status = run_workflow(model, [{"role": "user", "content": "demo"}], run, max_calls=1)
            self.assertEqual(status["tool_calls"], 1)
            self.assertEqual(run.results, {})

    def test_failed_data_does_not_create_report(self):
        with TemporaryDirectory() as folder:
            run = AnalysisRun(DATA / "anomalies.csv", Path(folder), True, log=lambda _: None)
            status = run_workflow(local_request(), [{"role": "user", "content": "demo"}], run)
            self.assertEqual(status["tool_calls"], 2)
            self.assertNotIn("create_report", run.results)

    def test_deepseek_sdk_request_contract(self):
        client = Mock()
        reply = Mock()
        reply.model_dump.return_value = {"content": "done"}
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=reply)]
        )
        messages = [{"role": "user", "content": "demo"}]
        self.assertEqual(deepseek_request(client)(messages, "none"), {"content": "done"})
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "deepseek-flash")
        self.assertEqual(kwargs["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(kwargs["tool_choice"], "none")
        self.assertEqual(kwargs["messages"], messages)
        self.assertEqual(len(kwargs["tools"]), 5)

    def test_resume_when_model_finishes_before_report(self):
        with TemporaryDirectory() as folder:
            run = AnalysisRun(DEMO, Path(folder), True, log=lambda _: None)
            choices = []

            def model(messages, choice):
                choices.append(choice)
                if len(choices) == 2:
                    return {"tool_calls": [call("read_arg_excel", "resume")]}
                return {"content": "done"}

            status = run_workflow(model, [{"role": "user", "content": "需要报告"}], run,
                                  max_calls=1, require_report=True)
            self.assertEqual(choices, [
                "auto", {"type": "function", "function": {"name": "read_arg_excel"}}, "none",
            ])
            self.assertEqual(status["tool_calls"], 1)
            self.assertIn("read_arg_excel", run.results)
