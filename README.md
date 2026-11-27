# AI Agent Security Benchmark

AI Agent Security Benchmark evaluates whether language models follow the instructions of a simulated e-commerce assistant when exposed to prompt injection. It covers two outcomes.

- **Domain hijacking** occurs when the assistant fulfills a request outside its intended store domain.
- **Tool misuse** occurs when the assistant uses a tool in a way that violates the policy for the current session.

## How it works

`StoreAgent` answers customer messages and can use tools to read store documents, manage orders, and update catalog prices. The benchmark runner sends messages from JSON scenarios to `StoreAgent` and records its replies, tool activity, and snapshots of the simulated store before and after each trial.

The runner validates the configuration and scenarios with Pydantic. Each trial starts with a fresh SQLite database. The benchmark supports evaluation by LLM judges and deterministic checks. The runner writes one JSON report per tested model configuration to `<results_dir>/<run-id>/<model-id>.json`.

## Run the benchmark

Install the Python dependencies in your project environment and run the benchmark from the repository root. [Dependencies](requirements.txt)

```powershell
py main.py
```

The default command loads `config/runner.json`. Use `--config` to select a different configuration file.

```powershell
py main.py --config path/to/runner.json
```

The runner configuration selects the scenarios, tested models, judge model, and number of repetitions. Each scenario describes a conversation and the criteria used to evaluate it. [Running experiments](docs/running-experiments.md)

## Documentation

- [Architecture and StoreAgent tools](docs/architecture.md)
- [Runner configuration schema](docs/schemas/runner-config.md)
- [Scenario schema](docs/schemas/scenario.md)
- [Result schema](docs/schemas/result.md)
