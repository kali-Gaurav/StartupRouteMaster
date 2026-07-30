"""
Partner health check task — disabled.

This file previously polled partner redirect targets and updated cache state.
Per the request to remove partner/redirect integration the task is now a no-op
that logs that partner checks are disabled. Keeping the async function exists
so scheduled runners that import it do not error.
"""

import logging
import asyncio

logger = logging.getLogger(__name__)


async def run_partner_health_check_task():
    logger.info("Partner health check task disabled — partner/redirect integrations removed.")
    # short sleep to behave like an async task
    await asyncio.sleep(0)
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_partner_health_check_task())
