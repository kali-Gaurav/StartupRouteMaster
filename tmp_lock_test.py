
import asyncio
import logging

class TestSingleton:
    _instance = None
    _lock = asyncio.Lock() # This might be the issue

    def __new__(cls):
        print("DEBUG: __new__ called")
        if cls._instance is None:
            cls._instance = super(TestSingleton, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        print("DEBUG: __init__ called")

async def main():
    print("DEBUG: Calling TestSingleton()")
    t = TestSingleton()
    print("DEBUG: Success")

if __name__ == "__main__":
    asyncio.run(main())
