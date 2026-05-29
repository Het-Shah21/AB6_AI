#!/usr/bin/env python3
"""Periodic population benchmark recalculation."""

import asyncio
import logging

from src.memory.population_benchmarks import PopulationBenchmarkService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Recalculating population benchmarks...")
    svc = PopulationBenchmarkService()
    result = await svc.recalculate_all()
    logger.info("Benchmark update complete: %s", result)


if __name__ == "__main__":
    asyncio.run(main())
