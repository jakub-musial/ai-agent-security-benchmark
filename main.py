import argparse
import asyncio
import logging

from src.benchmark.runner import load_config, run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the benchmark.")
    parser.add_argument(
        "--config",
        default="config/runner.json",
        help="Path to the runner configuration JSON file (default: %(default)s).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = load_config(args.config)
    asyncio.run(run_benchmark(config))


if __name__ == "__main__":
    main()
