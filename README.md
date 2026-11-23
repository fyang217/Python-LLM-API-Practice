# Python LLM API Practice

A Python CLI project for practicing **DeepSeek API integration, function calling, and automated evaluation**. It includes two small API exercises and a reproducible offline workflow that turns a synthetic data table into validated summaries, charts, and a Word report.

## What it demonstrates

| Capability | Implementation |
| --- | --- |
| API requests and responses | Uses the OpenAI Python SDK against DeepSeek. Shows a system prompt, prompt submission, and handling of empty responses, connection errors, and API status errors. |
| Function calling | Parses and validates model-supplied arguments, runs registered Python functions, and returns results with the matching tool-call ID. The analysis workflow caps execution at eight calls. |
| Data processing | Loads the bundled synthetic Excel or CSV, checks input quality, computes descriptive comparisons, and generates three PNG charts and a Word report. |
| Automated tests | **15 tests** cover the mocked API request contract, tool validation and recovery, default and explicit file paths, statistics, and report output. |

**Stack** · Python 3.12, DeepSeek API, OpenAI Python SDK, pandas, openpyxl, Matplotlib, python-docx, python-dotenv, and unittest.

## Run offline

From the repository root in PowerShell with Python 3.12 installed:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m agent.agent demo
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The demo uses the packaged synthetic workbook and needs no API key. It writes charts, a report, and a tool log under `outputs/`. The helpers also accept explicit Excel or CSV paths.

## Try the DeepSeek API

Copy [`.env.example`](.env.example) to `.env` and set your own `DEEPSEEK_API_KEY`. The first two commands are manual examples. The automated tests are in [`tests/`](tests/).

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe test_deepseek.py
.\.venv\Scripts\python.exe test_function_calling.py
.\.venv\Scripts\python.exe -m agent.agent deepseek
```

- [System prompt and chat request](test_deepseek.py) sends the current question to DeepSeek.
- [Function-calling example](test_function_calling.py) demonstrates a model-requested arithmetic function and the follow-up response.
- [Analysis workflow](agent/workflow.py) runs the registered tools across multiple turns within one task. It sends prompts and synthetic tool results to DeepSeek in API mode.

The demo uses synthetic data and reports descriptive, unpaired comparisons. Each chat request starts fresh, while tool messages persist within a single workflow task.
