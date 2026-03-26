---
name: "execute-unit-tests"
description: "Interpret user prompts and run only the relevant pytest unit tests"
---

# Unit Test Executor Skill

This skill interprets natural-language prompts and maps them to specific pytest invocations covering the `tests/` directory of the Alita SDK. It always runs only the tests that match the user's intent — never the full suite unless explicitly asked.

---

## Workflow

1. **Parse** the user's prompt to determine scope (file, class, method, keyword, tag).
2. **Map** keywords to concrete test paths using the reference tables below.
3. **Build** the minimal pytest command that covers only the requested tests.
4. **Run** with `runTests` tool (preferred) or terminal fallback.
5. **Report** results and suggest next steps on failures.

---

## Prerequisites

Always activate the virtualenv before running in terminal:

```bash
# Windows (Git Bash / bash)
source venv/Scripts/activate

# Linux / macOS
source venv/bin/activate
```

---

## Test Inventory

### `tests/runtime/` — Unit tests (no network, no credentials)

| File | Classes / key topics |
|------|---------------------|
| `tests/runtime/test_alita_llm.py` | `TestMaxRetriesExceededError`, `TestAlitaLLMConstants`, `TestAlitaLLMErrorHandling`, `TestUtilityFunctions`, `TestTypeHints` — LLM error handling, imports, type hints |
| `tests/runtime/test_blocked_tools.py` | `TestBlocklistConfiguration`, `TestFilterBlockedTools`, `TestFinalBlockedToolsFilter`, `TestInvokeToolBlockedGate` — tool/toolkit blocklist logic |
| `tests/runtime/test_logging_utils.py` | Streamlit callback handler, `setup_streamlit_logging`, `dispatch_custom_event`, `evaluate_template` — logging and template utilities |
| `tests/runtime/test_preloaded_model.py` | `TestPreloadedChatModel` — `count_tokens`, `remove_non_system_messages`, `limit_tokens` |
| `tests/runtime/test_prompt_client.py` | `TestAlitaPrompt` — prompt init, `create_pydantic_model`, `predict` |
| `tests/runtime/test_sandbox_sensitive_guard.py` | `TestSandboxToolMatching`, `TestCouldBeSensitive` — sandbox/sensitive tool detection |
| `tests/runtime/test_save_dataframe.py` | DataFrame save utilities |
| `tests/runtime/test_sensitive_tool_masking.py` | Sensitive value masking in tool args |
| `tests/runtime/test_streamlit_utils.py` | Streamlit UI helper functions |
| `tests/runtime/test_utils.py` | General SDK utility functions |
| `tests/runtime/test_utils_constants.py` | Utility constants |

### `tests/runtime/langchain/document_loaders/` — Parametrized loader tests

All four loaders follow the same structure — see the `document-loader-tests` skill for full details.

| File | Loader |
|------|--------|
| `test_alita_text_loader.py` | `AlitaTextLoader` |
| `test_alita_csv_loader.py` | `AlitaCSVLoader` |
| `test_alita_json_loader.py` | `AlitaJSONLoader` |
| `test_alita_markdown_loader.py` | `AlitaMarkdownLoader` |

### `tests/` — Integration / analysis tests (require credentials)

| File | Scope |
|------|-------|
| `tests/test_github_analysis.py` | GitHub toolkit analysis |
| `tests/test_gitlab_analysis.py` | GitLab toolkit analysis |
| `tests/test_ado_analysis.py` | Azure DevOps toolkit analysis |
| `tests/test_jira_analysis.py` | JIRA toolkit analysis |

---

## Keyword → Test Path Mapping

Use this table to translate user prompt keywords into pytest targets.

| User says… | Target path / flag |
|---|---|
| "all tests" | `tests/` |
| "all unit tests" | `tests/runtime/` |
| "llm", "alita llm", "max retries", "retry" | `tests/runtime/test_alita_llm.py` |
| "blocked tools", "blocklist", "toolkit blocking" | `tests/runtime/test_blocked_tools.py` |
| "logging", "streamlit logging", "callback handler", "evaluate template" | `tests/runtime/test_logging_utils.py` |
| "preloaded model", "count tokens", "limit tokens", "remove messages" | `tests/runtime/test_preloaded_model.py` |
| "prompt client", "alita prompt", "predict" | `tests/runtime/test_prompt_client.py` |
| "sandbox", "sensitive guard", "could be sensitive" | `tests/runtime/test_sandbox_sensitive_guard.py` |
| "save dataframe", "dataframe" | `tests/runtime/test_save_dataframe.py` |
| "sensitive masking", "tool masking", "mask" | `tests/runtime/test_sensitive_tool_masking.py` |
| "streamlit utils", "streamlit helpers" | `tests/runtime/test_streamlit_utils.py` |
| "utils", "utilities" | `tests/runtime/test_utils.py` |
| "constants", "utils constants" | `tests/runtime/test_utils_constants.py` |
| "text loader", "alita text" | `tests/runtime/langchain/document_loaders/test_alita_text_loader.py` |
| "csv loader", "alita csv" | `tests/runtime/langchain/document_loaders/test_alita_csv_loader.py` |
| "json loader", "alita json" | `tests/runtime/langchain/document_loaders/test_alita_json_loader.py` |
| "markdown loader", "alita markdown" | `tests/runtime/langchain/document_loaders/test_alita_markdown_loader.py` |
| "document loaders", "loaders" | `tests/runtime/langchain/document_loaders/` |
| "github analysis" | `tests/test_github_analysis.py` |
| "gitlab analysis" | `tests/test_gitlab_analysis.py` |
| "ado analysis", "azure devops analysis" | `tests/test_ado_analysis.py` |
| "jira analysis" | `tests/test_jira_analysis.py` |

---

## Targeting Specific Classes and Methods

Use pytest's `::` separator to narrow scope.

```bash
# Run a specific class
python -m pytest tests/runtime/test_blocked_tools.py::TestBlocklistConfiguration -v

# Run a specific method
python -m pytest tests/runtime/test_alita_llm.py::TestMaxRetriesExceededError::test_default_message -v

# Run by keyword expression (matches names of classes, functions, params)
python -m pytest tests/runtime/ -k "token" -v
python -m pytest tests/runtime/ -k "sensitive" -v
python -m pytest tests/runtime/ -k "TestAlitaPrompt and predict" -v
```

---

## Running Tests — Preferred Method

Use the `runTests` tool when possible. Pass the absolute file path(s) and optionally the test names.

**Examples based on user prompts:**

| Prompt | `files` param | `testNames` param |
|---|---|---|
| "run blocked tools tests" | `["…/tests/runtime/test_blocked_tools.py"]` | *(omit)* |
| "run TestBlocklistConfiguration" | `["…/tests/runtime/test_blocked_tools.py"]` | `["TestBlocklistConfiguration"]` |
| "run test_default_message in alita llm" | `["…/tests/runtime/test_alita_llm.py"]` | `["test_default_message"]` |
| "run all llm and prompt tests" | `["…/tests/runtime/test_alita_llm.py", "…/tests/runtime/test_prompt_client.py"]` | *(omit)* |
| "run the token-related tests" | `["…/tests/runtime/test_preloaded_model.py"]` | `["test_count_tokens_string", "test_count_tokens_message_list", "test_limit_tokens_no_limit_needed", "test_limit_tokens_with_limiting"]` |

---

## Terminal Fallback Commands

Use these when the `runTests` tool is unavailable or when you need tag/marker filtering.

```bash
# Single file
python -m pytest tests/runtime/test_blocked_tools.py -v

# Specific class
python -m pytest tests/runtime/test_alita_llm.py::TestMaxRetriesExceededError -v

# Specific method
python -m pytest tests/runtime/test_logging_utils.py::test_evaluate_template_context_variables -v

# Keyword filter across all unit tests
python -m pytest tests/runtime/ -k "token" -v

# Multiple files
python -m pytest tests/runtime/test_alita_llm.py tests/runtime/test_prompt_client.py -v

# Loader tests with tag
python -m pytest tests/runtime/langchain/document_loaders/ -m "loader_csv and feature_chunking" -v

# Stop on first failure
python -m pytest tests/runtime/test_blocked_tools.py -x -v

# Run last failed only
python -m pytest tests/runtime/ --lf -v
```

---

## Interpreting Ambiguous Prompts

When the prompt does not map to a single file or class, apply these heuristics in order:

1. **Exact name match** — if the user mentions a class name (`TestAlitaPrompt`) or function name (`test_predict_with_variables`), use `-k` option or `::` targeting.
2. **Topic keyword** — map the topic (e.g. "masking", "tokens", "sandbox") to the relevant file using the keyword table above.
3. **Multiple topics** — pass multiple file paths to `runTests` or chain them in one pytest command.
4. **Still ambiguous** — ask the user to clarify before running.

---

## Decision Tree

```
User prompt received
       │
       ▼
Does it mention a specific test name/class?
  YES ─► use ::ClassName::method_name targeting
  NO  ─► extract topic keywords
             │
             ▼
       Map keywords → file path(s)
             │
             ▼
       Single file? ──YES──► runTests with that file
             │
            NO
             ▼
       Multiple files ──► runTests with list OR chain pytest paths
             │
             ▼
       Loader tests involved? ──YES──► check if marker -m filter applies
             │
            NO
             ▼
       Run and report results
```

---

## After Running Tests

- If **all pass**: confirm to the user and list the test count.
- If **some fail**: show the failure summary, point to the file + class + method, and suggest whether to run with `-x` (stop-on-first-fail) or `--lf` (last-failed).
- If **import error / collection error**: the virtualenv is likely not activated or a dependency is missing — instruct the user to activate it and re-run.
- If **credential / network error** (integration tests only): advise the user to verify `.env` values before re-running.
