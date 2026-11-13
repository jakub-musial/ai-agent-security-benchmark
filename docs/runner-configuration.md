# Runner configuration

`config/runner.json` defines the scenarios, model configurations, repetitions, and output directory for a benchmark run. This document specifies the intended configuration contract.

## Example

```json
{
  "scenarios": [
    "scenarios/dh_001.json",
    "scenarios/tm_001.json"
  ],
  "repetitions": 3,
  "models": [
    {
      "id": "sol-medium",
      "backend": "openai_oauth",
      "model": "<model-identifier>",
      "settings": {
        "reasoning_effort": "medium"
      }
    },
    {
      "id": "gemma3-4b",
      "backend": "ollama",
      "model": "gemma3:4b",
      "settings": {
        "temperature": 0.7
      }
    }
  ],
  "results_dir": "results"
}
```

Replace `<model-identifier>` with an identifier accepted by the selected backend. The Ollama example requires the named model to be available on the configured server.

## Root fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `scenarios` | Array of strings | Yes | Non-empty list of paths to scenario JSON files. Each scenario runs against every model configuration. |
| `repetitions` | Integer | Yes | Number of independent trials for each scenario and model configuration pair. Must be at least `1`. |
| `models` | Array of objects | Yes | Non-empty list of model configurations described below. |
| `results_dir` | String | Yes | Output directory. Each runner invocation creates a separate subdirectory for its results. |

Relative paths are resolved from the project root, including paths in `scenarios` and `results_dir`.

## Model fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | String | Yes | Non-empty label identifying this configuration in results. Must be unique within `models`. Different settings for the same model use different IDs. |
| `backend` | String | Yes | Connection backend. Accepted values are `openai_oauth` and `ollama`. |
| `model` | String | Yes | Non-empty model identifier accepted by the backend. For Ollama, use the full model name, including its tag, such as `gemma3:4b`. |
| `settings` | Object | No | Generation settings supported by the selected backend and model. Omission or `{}` uses backend and model defaults. |

The runner translates configuration settings into the parameters required by the backend integration.

### Generation settings

| Field | Type | Description |
| --- | --- | --- |
| `reasoning_effort` | String | Reasoning level for models supporting this control through the OpenAI OAuth backend. Accepted levels depend on the model. |
| `temperature` | Number | Sampling randomness for models supporting this parameter. Lower values generally produce less varied responses. |
| `think` | Boolean or string | Ollama thinking control, where supported. A boolean selects on/off behavior, while a string selects a model-supported reasoning level. |

Each configuration includes only settings supported by its backend and model. Unsupported settings must produce a configuration error. Temperature and reasoning controls govern different aspects of generation.

## Loading and validation

Pass the configuration path explicitly to `load_config` in `src/benchmark/runner.py`. The function returns a `RunnerConfig` defined in `src/benchmark/config.py`.

```python
from src.benchmark.runner import load_config

config = load_config("config/runner.json")
```

The configuration file path is resolved relative to the working directory. Paths stored inside the configuration retain their project-relative values.

Validation rejects malformed JSON, missing required fields, unknown fields, incorrect types, blank strings, empty scenario or model lists, non-positive repetition counts, and duplicate model configuration IDs. Numeric strings and booleans are rejected for `repetitions`. Surrounding whitespace is stripped from IDs, model names, paths, and named generation controls.

Generation settings are optional. Temperature must be finite and non-negative. The configuration format accepts `reasoning_effort` for `openai_oauth` and `think` for `ollama`.

This initial loader validates configuration data. Scenario file existence and content, model availability, and model-specific setting support will be checked when execution is implemented. Malformed JSON and invalid values raise `pydantic.ValidationError`. File access and UTF-8 decoding errors propagate to the caller.

## Trial semantics

The total number of trials is `scenario count × model configuration count × repetitions`. Every trial starts with a fresh sandbox and conversation history. A failed execution is recorded as an execution error, independently of the attack outcome.
