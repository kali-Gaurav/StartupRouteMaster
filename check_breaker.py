import asyncio
from backend.providers.circuit_breaker import AsyncCircuitBreaker

async def sample_func(x):
    return x * 2

async def main():
    breaker = AsyncCircuitBreaker()
    # Should work now with def __call__
    wrapper = breaker(sample_func)
    print(f"Wrapper type: {type(wrapper)}")
    result = await wrapper(10)
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
