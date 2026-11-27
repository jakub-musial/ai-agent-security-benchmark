# Running experiments

## Run the benchmark

Run these commands from the repository root with the project environment active and the dependencies installed. [Python dependencies](../requirements.txt)

`py main.py` loads `config/runner.json` by default. Add at least one scenario to its `scenarios` list before running it.

```powershell
py main.py
```

To use a different runner configuration, pass its path with `--config`.

```powershell
py main.py --config path/to/runner.json
```

## Configure a run

- `scenarios` lists the scenario JSON files to run.
- `models` lists the configurations to test, including the backend, model name, result ID, and optional generation settings.
- `judge_model` selects the shared model used by `ResponseJudge` and `ToolJudge`.
- `repetitions` sets how many times each scenario runs for each tested model.
- `results_dir` sets the directory where the runner writes reports.

The runner supports two backends. `ollama` runs models locally through Ollama. When a tested model or the judge uses `openai_oauth`, the runner opens a browser for OpenAI sign-in. [Runner configuration schema](schemas/runner-config.md)

## Prepare a scenario

Give the scenario an `id` that is unique within the run and set its `objective` to `domain_hijacking` or `tool_misuse`. List the conversation turns in `prompts`. Each turn can contain `text`, attachment paths in `files`, or both. Keep text files and images under `scenarios/attachments/`, list their paths relative to `scenarios/`, and use formats supported by the tested models. [Scenario schema](schemas/scenario.md#fields)

Supply at least one of the two LLM criteria. Describe an observable outcome for each criterion you include.

- `response_criterion` tells `ResponseJudge` what to look for in `StoreAgent`'s replies.
- `tool_criterion` tells `ToolJudge` what to look for in recorded tool calls, returns, or store state.
- Optional `tool_expectations.checks` list the tool events or persistent database changes that `ToolExpectationsEvaluator` checks deterministically. The `match` field controls whether all checks or any check must pass.

The report records each evaluator's results separately. [Automatic evaluations](schemas/result.md#automatic-evaluations)

## Find the reports

The runner writes one JSON report per tested model configuration to `<results_dir>/<run-id>/<model-id>.json`. Each report covers that model's repetitions across the selected scenarios. `report.cases` contains completed trials and their evaluations. `report.failures` contains trial execution errors. Read each verdict against the criterion it evaluates. [Result schema](schemas/result.md#interpretation)
