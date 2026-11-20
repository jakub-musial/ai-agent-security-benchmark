# Runner configuration JSON schema

`RunnerConfig`, defined in [`src/benchmark/schemas/config.py`](../src/benchmark/schemas/config.py), describes a benchmark run: the selected scenarios, tested models, judge model, repetition count, and output directory. The runner reads this configuration from a UTF-8 JSON file, such as `config/runner.json`.

## Example

```json
{
  "scenarios": [
    "scenarios/dh_001.json"
  ],
  "repetitions": 2,
  "models": [
    {
      "id": "openai-medium",
      "backend": "openai_oauth",
      "model": "<model-identifier>",
      "settings": {
        "reasoning_effort": "medium"
      }
    },
    {
      "id": "gemma-local",
      "backend": "ollama",
      "model": "gemma3:4b",
      "settings": {
        "temperature": 0.7
      }
    }
  ],
  "judge_model": {
    "id": "judge",
    "backend": "ollama",
    "model": "gemma3:4b",
    "settings": {
      "temperature": 0.0
    }
  },
  "results_dir": "results"
}
```

Replace `<model-identifier>` with a model available through the OpenAI OAuth backend. Ollama model names must refer to models available on the server.

## Fields

| Field | JSON type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `scenarios` | array of strings | Yes | — | Non-empty list of paths to [scenario files](scenario-configuration.md). Each scenario runs against every entry in `models`. |
| `repetitions` | integer | Yes | — | Number of independent executions of each scenario for each tested model. Minimum: `1`. |
| `models` | array of objects | Yes | — | Non-empty list of tested model configurations. Each entry uses the model fields below. |
| `judge_model` | object | Yes | — | Model configuration used by the LLM judge to assess attack success. Uses the same fields as an entry in `models`. |
| `results_dir` | string | Yes | — | Output directory. Each run creates a subdirectory named `YYYY-MM-DD_HH-MM-SS_microseconds` containing one [result file](result-schema.md) per tested model. |

Relative paths in `scenarios` and `results_dir` are resolved from the working directory, not from the configuration file's directory.

### Model configuration

Each entry in `models` and the `judge_model` object uses `ModelConfig`.

| Field | JSON type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | string | Yes | — | Configuration identifier. Used as the report name and the result filename: `<id>.json`. Must be unique within `models`; `judge_model.id` may match a tested model's ID. |
| `backend` | string | Yes | — | Connection backend: `openai_oauth` or `ollama`. |
| `model` | string | Yes | — | Model identifier accepted by the backend, such as `gemma3:4b` for Ollama. |
| `settings` | object | No | `{}` | Generation settings described below. Omission or an empty object leaves all generation controls unset. |

### Generation settings

The `settings` object uses `GenerationSettings`. An omitted field or `null` leaves that control to the backend and model defaults.

| Field | JSON type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `reasoning_effort` | string or null | No | `null` | Reasoning level for `openai_oauth`. Accepted levels depend on the model. Rejected for `ollama`; use `think` instead. |
| `temperature` | number or null | No | `null` | Sampling temperature for `ollama`. Must be finite and non-negative. The current `openai_oauth` integration rejects non-null values when creating the model. |
| `think` | boolean, string, or null | No | `null` | Reasoning control for `ollama`. `true` maps to reasoning effort `medium`; `false` maps to `none`; strings are forwarded as named reasoning levels. Rejected for `openai_oauth`. |

## Validation

Unknown fields and incorrect JSON types are rejected in all configuration objects. Required strings must contain non-whitespace text. Surrounding whitespace is stripped from IDs, model names, paths, and named generation controls. `repetitions` accepts only an integer; numeric strings and booleans are rejected.

`load_config` validates the configuration structure, field constraints, model ID uniqueness, and backend compatibility of `reasoning_effort` and `think`. Malformed JSON or invalid configuration data raises `pydantic.ValidationError`. File access and UTF-8 decoding errors propagate to the caller.

Scenario files are loaded and scenario IDs are checked for uniqueness when the benchmark starts. Model availability and support for individual generation levels depend on the backend and model and are not verified by configuration validation.

## Interpretation

The number of scenario executions is `len(scenarios) × len(models) × repetitions`. The judge evaluates these executions; it does not add scenario executions of its own.

Each execution runs the scenario's entire prompt list with a fresh sandbox, agent, and conversation history. State is shared between turns within that execution and reset before the next execution. Execution errors are recorded separately from attack verdicts in the [result schema](result-schema.md).
