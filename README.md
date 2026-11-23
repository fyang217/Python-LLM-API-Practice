# Python LLM API Practice

A Python CLI project for learning how to call the DeepSeek API, use a system prompt, and pass validated Python tool results back to a model. The project includes small API exercises and a bounded workflow that analyzes a synthetic antibiotic resistance gene (ARG) abundance table.

## Implemented

| Entry point | What it demonstrates |
| --- | --- |
| `test_deepseek.py` | Sends a system prompt and the current question to DeepSeek through the OpenAI-compatible Python SDK. The terminal accepts repeated questions. Each API request starts with a fresh message list. |
| `test_function_calling.py` | Lets the model request a small arithmetic tool, checks the arguments, and sends the tool result back to the model. |
| `python -m agent.agent demo` | Runs a deterministic, offline pipeline for data validation, sample totals, descriptive comparisons, plots, and a Word report. |
| `python -m agent.agent deepseek` | Runs a multi-step model–tool exchange for one task. Python validates registered tool calls, returns each result with its tool-call ID, and caps execution at eight tool calls. |

The workflow starts with a system prompt and a user task. In DeepSeek mode, the model chooses the next registered tool. Python checks the request, runs the tool, and appends its result to the message list. Python also computes the values shown in the terminal and generated report. The API demo uses the bundled synthetic workbook.

## Stack and structure

Python 3.12, OpenAI Python SDK for the DeepSeek endpoint, python-dotenv, pandas, openpyxl, Matplotlib, python-docx, and unittest.

| Path | Role |
| --- | --- |
| `agent/agent.py`, `agent/prompts.py`, `agent/workflow.py` | CLI, system prompt, and tool execution |
| `arg_analysis_tools.py`, `tools/` | Input checks, abundance summaries, comparison, plots, and report generation |
| `data/demo/` | Synthetic Excel and CSV inputs, an anomaly fixture, and independent expected results |
| `tests/` | Automated data, workflow, statistics, and reporting checks |

## Run locally

From the repository root in PowerShell, with Python 3.12 installed:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m agent.agent demo
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The offline demo needs no API key. Each run writes its report, three PNG charts, structured results, and tool-call log to a separate folder under `outputs/`.

To run an API exercise, copy the example environment file, set `DEEPSEEK_API_KEY` in the local `.env`, and choose an entry point:

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe test_deepseek.py
.\.venv\Scripts\python.exe test_function_calling.py
.\.venv\Scripts\python.exe -m agent.agent deepseek
```

In DeepSeek mode, press Enter to use the built-in task. The online examples require a network connection and a usable DeepSeek account. They send your prompt to DeepSeek, and the analysis workflow also sends synthetic tool results. Use non-sensitive prompts.

## Limits

- The message history for a workflow lasts for one task. The interactive API script does not retain prior user turns, and neither entry point persists chat history.
- The sample data are synthetic and intended for verifying the workflow. Group comparisons are descriptive and unpaired, with no significance tests. Summed normalized abundances cannot establish absolute gene copy numbers.
- The workflow exposes a fixed set of Python tools. The demo uses a specific sample-header convention and a single-sheet CLI input. Model tool choices depend on the prompt and the API response.
- The automated tests exercise the API adapter with a mock. The live scripts require separate execution and credentials.

## Future work

- Add optional, in-memory user conversation history and tests for context carryover.
- Add more simulated inputs and test additional API failure cases.
- Record latency and token use for repeatable API evaluations.
