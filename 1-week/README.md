# Tool-Calling Chat Agent

This project is an interactive terminal chat agent that uses OpenRouter through
the OpenAI Python SDK. The agent keeps conversation history, lets the model
select registered tools, executes those tools locally, and sends their results
back to the model.

## Setup

Python 3.10 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=your_openrouter_api_key
# Required when the agent uses search_web
BRAVE_SEARCH_API_KEY=your_brave_search_api_key
# Optional: directory available to file-system tools
AGENT_FILES_ROOT=agent_files
# Optional: replace the run_shell executable allowlist (comma-separated)
# SHELL_ALLOWED_COMMANDS=cat,grep,head,ls,printf,pwd,tail,wc
```

The `run_shell` tool is Linux-only and requires Bubblewrap. On Arch Linux:

```bash
sudo pacman -S bubblewrap
```

Verify it is available with `command -v bwrap`.

## Running the chat

Activate the virtual environment and start the application:

```bash
source .venv/bin/activate
python main.py
```

You can also run it without activating the environment:

```bash
.venv/bin/python main.py
```

Enter `exit` or `quit` to stop the chat.

When the model selects a tool, the application prints its name before execution:

```text
[tool] Starting search_web
```

Only the tool name is displayed; arguments and file contents are not printed.

## Tools

Tools are stored in the `tools/` package:

```text
tools/
├── file_system/
│   ├── delete_file_tool.py
│   ├── list_files_tool.py
│   ├── path_guard.py
│   ├── read_file_tool.py
│   └── write_file_tool.py
├── weather_tool/
│   └── weather_tool.py
├── shell_tool/
│   └── shell_tool.py
├── web_search/
│   └── web_search_tool.py
├── tool.py
└── tool_registry.py
```

### Tool interface

Every tool implements the abstract `Tool` interface from `tools/tool.py`:

```python
class Tool(ABC):
    @property
    def name(self) -> str:
        ...

    @property
    def definition(self) -> dict[str, Any]:
        ...

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        ...
```

- `name` is the function name exposed to the model.
- `definition` is the OpenAI-compatible JSON schema describing the tool and
  its arguments.
- `execute` validates the model-provided arguments and returns structured data.

`ToolRegistry` holds the available tools, sends their definitions to the model,
and dispatches requested calls through this common interface. Only registered
tools can be executed.

### Weather tool

`WeatherTool` is registered as `get_weather`. It accepts one argument:

```json
{
  "city": "Tehran"
}
```

It uses the keyless Open-Meteo APIs to:

1. Convert the city name into coordinates.
2. Fetch the current conditions for those coordinates.
3. Return the location, observation time, timezone, condition, temperature,
   apparent temperature, humidity, precipitation, and wind speed.

Open-Meteo returns numeric WMO weather codes. The tool converts those codes
into readable conditions such as `Clear sky`, `Slight rain`, or `Thunderstorm`
before returning the result to the model.

The tool only provides current conditions. It is not intended for historical
weather, long-range forecasts, or general climate questions.

### File-system tools

The application registers four file-system tools:

- `read_file` reads a UTF-8 text file.
- `write_file` creates a UTF-8 text file or explicitly overwrites one.
- `list_files` lists a directory, optionally recursively.
- `delete_file` moves a file into protected trash after explicit confirmation.

All paths are relative to a sandbox root. The default root is `agent_files/` in
the project directory. Override it with `AGENT_FILES_ROOT` in `.env` when the
agent should use a different directory.

The tools enforce the following restrictions:

- Absolute paths and `..` traversal are rejected.
- Symbolic links cannot be read, written through, or deleted.
- The protected `.trash` directory is hidden from tool access and listings.
- Reads and writes are limited to 1,000,000 bytes.
- Directory listings are limited to 200 entries and report when truncated.
- Existing files are not replaced unless `overwrite` is explicitly `true`.
- Deletion only accepts files, requires `confirm: true`, and is recoverable from
  the sandbox's `.trash` directory.

Examples of user requests:

```text
Write "hello" to notes/greeting.txt.
Read notes/greeting.txt.
List all files recursively.
Delete notes/greeting.txt.
```

The delete tool schema instructs the model to set `confirm: true` only after the
user explicitly requests deletion of that specific file.

### Web search tool

`WebSearchTool` is registered as `search_web`. It uses the Brave Web Search API
and requires `BRAVE_SEARCH_API_KEY` in `.env`.

The tool accepts three required arguments:

```json
{
  "query": "latest Python release",
  "count": 5,
  "freshness": "month"
}
```

- `query` is limited to 600 characters and 75 words.
- `count` must be between 1 and 10.
- `freshness` must be `any`, `day`, `week`, `month`, or `year`.

Safe search is always set to `moderate`. Results contain a title, URL, short
snippet, and optional age. HTML markup is removed, large fields are truncated,
and the response marks all result content as untrusted external text so the
agent does not follow instructions embedded in search results.

Example request:

```text
Search the web for the latest Python release and give me the source links.
```

For local API simulations, the endpoint can be overridden without changing
code:

```env
BRAVE_SEARCH_BASE_URL=http://127.0.0.1:4900/search/v1/web/search
```

### Shell tool

`ShellTool` is registered as `run_shell`. It runs one executable with a
structured argument array:

```json
{
  "argv": ["grep", "-n", "error", "logs/app.txt"],
  "working_directory": ".",
  "timeout_seconds": 5
}
```

It deliberately does not accept a shell command string. Characters such as
`|`, `>`, `&&`, `$()`, and backticks are passed as ordinary argument text and
are never interpreted by a shell.

Every command runs inside a Bubblewrap sandbox with these restrictions:

- Only `AGENT_FILES_ROOT` is persistently writable; the rest of the project is
  not mounted, and `/tmp` is private and ephemeral.
- Network access is disabled.
- The parent process environment and secrets are cleared.
- The protected `.trash` directory is hidden.
- Execution time, output size, address space, and open files are limited.
- Standard input is closed, so commands must be non-interactive.
- Executables must be on the allowlist; `sh`, `bash`, destructive commands,
  package managers, and network clients are not allowed by default.

The default commands are intended for inspecting files and processing text.
Use the dedicated file-system tools for writes and deletion. Operators can
replace the allowlist with `SHELL_ALLOWED_COMMANDS`, a comma-separated list of
bare executable names. Expanding it to mutating commands allows those commands
to change files inside `AGENT_FILES_ROOT`, so treat that setting as a security
policy.

Example request:

```text
Use grep to find lines containing "error" in logs/app.txt.
```

## Evaluations

The evaluation suite uses [DeepEval](https://deepeval.com/) with OpenRouter as
both the agent provider and the LLM-judge provider. The cases are stored as
DeepEval `Golden` or `ConversationalGolden` objects and converted to
`LLMTestCase` or `ConversationalTestCase` objects after each agent run.

```text
evals/
├── deepeval_utils.py
├── recording_tool_registry.py
└── weather_tool/
    ├── mock_weather_tool.py
    ├── test_agent_responses.py
    ├── test_multi_turn_conversations.py
    ├── test_tool_selection.py
    └── weather_fixtures.py
```

`ToolCorrectnessMetric` checks the exact tool list and normalized input
parameters. `GEval` checks that complete-agent answers satisfy the case-specific
requirements and remain grounded in the fixed tool output. True multi-turn
conversations use DeepEval `ConversationalTestCase` objects and conversational
metrics.

### Running the evals

From the project root, run:

```bash
source .venv/bin/activate
deepeval test run evals/weather_tool
```

Run only the first-decision tool-routing suite with:

```bash
deepeval test run evals/weather_tool/test_tool_selection.py
```

This suite contains 14 cases covering:

- Prompts that should call `get_weather`.
- Prompts that should not call any tool.
- City-argument extraction.
- Missing locations, historical weather, forecasts, climate questions, and
  general knowledge.

It stops after the first model response, so it never executes the weather tool
or calls Open-Meteo.

### Selecting the evaluation model

By default, evaluations use the application's `openrouter/free` model. This is
a router, so different cases may be handled by different underlying models.

For repeatable results, pin a tool-capable model for the eval:

```bash
EVAL_MODEL="provider/model-name" \
deepeval test run evals/weather_tool/test_tool_selection.py
```

You can also put the override in `.env`:

```env
EVAL_MODEL=provider/model-name
```

The tool-routing suite makes one live OpenRouter request per case. DeepEval's
strict tool metric is deterministic for these cases and does not make a judge
request.

### Evaluating complete single-interaction responses

The complete-agent suite runs the model-tool-model loop against a deterministic
mock weather tool. The mock returns fixed weather data and never calls
Open-Meteo.

Run it with:

```bash
EVAL_MODEL="provider/agent-model" \
JUDGE_MODEL="provider/judge-model" \
deepeval test run evals/weather_tool/test_agent_responses.py
```

`EVAL_MODEL` controls the agent being evaluated. `JUDGE_MODEL` controls the
DeepEval `GEval` metric that scores final-answer quality. If `JUDGE_MODEL` is
omitted, it defaults to the agent model. A separate pinned judge is more
reliable.

For each case, the evaluator verifies:

- The expected tools were called exactly once and in the expected order.
- Tool names and arguments match the case.
- No unexpected tool calls occurred.
- The final answer completed the task and stayed consistent with the fixed tool
  result.
- The final answer did not add unsupported weather claims.

A case passes only when the strict tool metric and the grounded-answer metric
both pass. DeepEval returns a nonzero exit code when any case fails and prints
the score and reason for each metric.

### Evaluating multi-turn conversations

The multi-turn suite reuses one `ChatApplication` instance across several user
messages so its conversation history is exercised. Each user and assistant
message becomes a DeepEval `Turn`; tool calls are attached to the assistant turn
that caused them.

Run it with:

```bash
EVAL_MODEL="provider/agent-model" \
JUDGE_MODEL="provider/judge-model" \
deepeval test run evals/weather_tool/test_multi_turn_conversations.py
```

The three scenarios cover:

- Resolving a follow-up question that does not repeat the city.
- Retaining weather details across progressive follow-up questions.
- Switching cities and comparing results without mixing their contexts.

Each conversation is evaluated with DeepEval's `ConversationCompletenessMetric`
for user-intention coverage, `ToolUseMetric` for tool selection and arguments
across turns, and `ConversationalGEval` for scenario-specific memory and
grounding.

DeepEval may create local run data under `.deepeval/`; this directory is ignored
by Git. Set `DEEPEVAL_TELEMETRY_OPT_OUT=1` if you also want to disable anonymous
DeepEval usage telemetry.
