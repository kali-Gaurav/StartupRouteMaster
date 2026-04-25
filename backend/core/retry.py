"""
Retry Utilities with Exponential Backoff

Provides decorators and utilities for retrying failed operations
with configurable backoff strategies.
"""

import asyncio
import functools
import logging
import random
from typing import Callable, Any, Optional, Type, Union

logger = logging.getLogger(__name__)


def retry(
    func: Optional[Callable] = None,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (Exception,),
    non_retryable_exceptions: tuple = (),
    conditions: Optional[list] = None,
    on_retry: Optional[Callable] = None,
    base_delay: Optional[float] = None,
) -> Callable:
    """
    Decorator for retrying async functions with exponential backoff.

    Supports both @retry and @retry(max_attempts=5).
    """
    def _create_decorator(
        max_attempts: int,
        initial_delay: float,
        max_delay: float,
        exponential_base: float,
        jitter: bool,
        retryable_exceptions: tuple,
        non_retryable_exceptions: tuple,
        conditions: Optional[list],
        on_retry: Optional[Callable]
    ) -> Callable:
        conditions_local = conditions or []

        def _should_retry(exc: BaseException) -> bool:
            if isinstance(exc, non_retryable_exceptions):
                return False
            if conditions_local:
                return any(condition(exc) for condition in conditions_local)
            return isinstance(exc, retryable_exceptions)

        def decorator(target_func: Callable) -> Callable:
            @functools.wraps(target_func)
            async def wrapper(*args, **kwargs) -> Any:
                last_exception = None
                for attempt in range(max_attempts):
                    try:
                        return await target_func(*args, **kwargs)
                    except BaseException as e:
                        if not _should_retry(e):
                            raise
                        last_exception = e
                        if attempt >= max_attempts - 1:
                            logger.error(f" {target_func.__name__} failed after {max_attempts} attempts: {e}")
                            raise
                        delay = min(initial_delay * (exponential_base ** attempt), max_delay)
                        if jitter:
                            delay = delay * (0.5 + random.random())
                        if on_retry:
                            try:
                                on_retry(attempt + 1, max_attempts, e, delay)
                            except Exception as callback_err:
                                logger.warning(f"on_retry callback failed: {callback_err}")
                        logger.warning(
                            f" {target_func.__name__} attempt {attempt + 1}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                if last_exception:
                    raise last_exception
                raise RuntimeError("Unexpected retry state")
            return wrapper
        return decorator

    effective_initial_delay = base_delay if base_delay is not None else initial_delay

    if callable(func):
        return _create_decorator(
            max_attempts,
            effective_initial_delay,
            max_delay,
            exponential_base,
            jitter,
            retryable_exceptions,
            non_retryable_exceptions,
            conditions,
            on_retry,
        )(func)

    return _create_decorator(
        max_attempts,
        effective_initial_delay,
        max_delay,
        exponential_base,
        jitter,
        retryable_exceptions,
        non_retryable_exceptions,
        conditions,
        on_retry,
    )


def retry_sync(
    func: Optional[Callable] = None,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (Exception,),
    non_retryable_exceptions: tuple = (),
    base_delay: Optional[float] = None,
) -> Callable:
    """Decorator for retrying sync functions."""
    def _create_decorator(
        max_attempts: int,
        initial_delay: float,
        max_delay: float,
        exponential_base: float,
        jitter: bool,
        retryable_exceptions: tuple,
        non_retryable_exceptions: tuple,
    ) -> Callable:
        def decorator(target_func: Callable) -> Callable:
            @functools.wraps(target_func)
            def wrapper(*args, **kwargs) -> Any:
                last_exception = None
                for attempt in range(max_attempts):
                    try:
                        return target_func(*args, **kwargs)
                    except non_retryable_exceptions:
                        raise
                    except retryable_exceptions as e:
                        last_exception = e
                        if attempt >= max_attempts - 1:
                            logger.error(f"❌ {target_func.__name__} failed after {max_attempts} attempts: {e}")
                            raise
                        delay = min(initial_delay * (exponential_base ** attempt), max_delay)
                        if jitter:
                            delay = delay * (0.5 + random.random())
                        logger.warning(
                            f"⚠️ {target_func.__name__} attempt {attempt + 1}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        import time
                        time.sleep(delay)
                if last_exception:
                    raise last_exception
                raise RuntimeError("Unexpected retry state")
            return wrapper
        return decorator

    effective_initial_delay = base_delay if base_delay is not None else initial_delay

    if callable(func):
        return _create_decorator(
            max_attempts,
            effective_initial_delay,
            max_delay,
            exponential_base,
            jitter,
            retryable_exceptions,
            non_retryable_exceptions,
        )(func)

    return _create_decorator(
        max_attempts,
        effective_initial_delay,
        max_delay,
        exponential_base,
        jitter,
        retryable_exceptions,
        non_retryable_exceptions,
    )


class RetryPolicy:
    """Configurable retry policy."""
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        conditions: Optional[list] = None,
        on_retry: Optional[Callable] = None,
        **kwargs
    ):
        self.max_attempts = max_attempts
        self.initial_delay = kwargs.get("base_delay", initial_delay)
        self.base_delay = self.initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.conditions = conditions or []
        self.on_retry = on_retry
        
        # Support retry_on_exceptions
        if "retry_on_exceptions" in kwargs:
            exc_types = kwargs["retry_on_exceptions"]
            self.conditions.append(lambda e: isinstance(e, exc_types))
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        last_exception = None
        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                should_retry = False
                for condition in self.conditions:
                    try:
                        if condition(e):
                            should_retry = True
                            break
                    except Exception: pass
                if not should_retry: raise
                if attempt >= self.max_attempts - 1: raise
                delay = min(self.initial_delay * (self.exponential_base ** attempt), self.max_delay)
                if self.jitter: delay = delay * (0.5 + random.random())
                if self.on_retry:
                    try: self.on_retry(attempt + 1, self.max_attempts, e, delay)
                    except Exception: pass
                await asyncio.sleep(delay)
        if last_exception: raise last_exception
        raise RuntimeError("Unexpected retry state")


# Common retry policies
RETRY_POLICY_FAST = RetryPolicy(
    max_attempts=3,
    initial_delay=0.1,
    max_delay=1.0,
    conditions=[
        lambda e: "timeout" in str(e).lower(),
        lambda e: "connection" in str(e).lower(),
    ]
)

RETRY_POLICY_EXTERNAL_API = RetryPolicy(
    max_attempts=5,
    initial_delay=1.0,
    max_delay=30.0,
    conditions=[
        lambda e: hasattr(e, 'status') and e.status >= 500,
        lambda e: "timeout" in str(e).lower(),
        lambda e: "rate limit" in str(e).lower(),
    ]
)

RETRY_POLICY_CRITICAL = RetryPolicy(
    max_attempts=6,
    initial_delay=0.5,
    max_delay=20.0,
    conditions=[
        lambda e: hasattr(e, 'status') and e.status >= 500,
        lambda e: "timeout" in str(e).lower(),
        lambda e: "connection" in str(e).lower(),
        lambda e: "rate limit" in str(e).lower(),
    ]
)

RETRY_POLICY_DATABASE = RetryPolicy(
    max_attempts=5,
    initial_delay=0.5,
    max_delay=5.0,
    conditions=[
        lambda e: "connection" in str(e).lower(),
        lambda e: "timeout" in str(e).lower(),
        lambda e: "deadlock" in str(e).lower(),
        lambda e: "operationalerror" in str(e).lower(),
    ]
)

# Aliases for backward compatibility
retry_async = retry