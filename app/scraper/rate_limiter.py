import asyncio
import random
from loguru import logger

class RateLimiter:
    def __init__(self, min_delay: float = 1.0, max_delay: float = 3.0):
        self.min_delay = min_delay
        self.max_delay = max_delay

    async def wait(self):
        """Attend un délai aléatoire pour éviter les blocages"""
        delay = random.uniform(self.min_delay, self.max_delay)
        logger.debug(f"Rate limiting: waiting {delay:.2f}s")
        await asyncio.sleep(delay)