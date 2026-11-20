import asyncio
import logging

from src.benchmark.runner import load_config, run_benchmark

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = load_config("config/runner.json")
    asyncio.run(run_benchmark(config))
