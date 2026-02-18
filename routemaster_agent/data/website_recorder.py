"""Advanced Playwright recorder with real website integration.

This module provides helper functions to record actual task demonstrations
from NTES and IRCTC websites using Playwright headless browser.

Features:
- Auto-detect page loads and element interactions
- Capture screenshots with action context
- Extract page metadata and form field info
- Support for complex multi-step workflows

Example:
  recorder = WebsiteRecorder()
  await recorder.record_ntes_schedule("search_trains_example", train_no="12345")
"""
from __future__ import annotations
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from routemaster_agent.data.scene_recorder import SceneRecorder


class WebsiteRecorder:
    def __init__(self, base_dir: str | Path = "datasets/raw_scenes"):
        self.base_dir = Path(base_dir)
        self.recorder = SceneRecorder(base_dir=self.base_dir)

    async def record_ntes_schedule(self, scene_id: str, train_no: str):
        """Record a NTES schedule lookup demonstration."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError("Playwright not installed. Install with: pip install playwright")

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Start recording
        await self.recorder.start_scene(
            scene_id,
            {"site": "ntes", "job_type": "schedule", "task": {"train_number": train_no}}
        )

        step = 1

        # Step 1: Navigate to NTES
        await page.goto("https://enquiry.indianrail.gov.in/mntes/", wait_until="networkidle", timeout=30000)
        await self.recorder.record_step(page, {"type": "navigate", "url": "https://enquiry.indianrail.gov.in/mntes/"}, step)
        step += 1
        await asyncio.sleep(2)

        # Step 2: Input train number
        try:
            await page.fill("input[name='txtTrainNo']", train_no, timeout=10000)
            await self.recorder.record_step(page, {"type": "input", "selector": "input[name='txtTrainNo']", "value": train_no}, step)
            step += 1
            await asyncio.sleep(1)
        except Exception as e:
            print(f"  ⚠ input field not found: {e}")

        # Step 3: Click search
        try:
            search_btn = page.locator("button:has-text('Search')")
            if await search_btn.count() > 0:
                await search_btn.click(timeout=10000)
                await self.recorder.record_step(page, {"type": "click", "selector": "button:has-text('Search')"}, step)
                step += 1
                await asyncio.sleep(3)
        except Exception as e:
            print(f"  ⚠ search button not found: {e}")

        # Step 4: Wait for results (if available)
        try:
            await page.wait_for_selector("table", timeout=5000)
            await self.recorder.record_step(page, {"type": "wait", "selector": "table"}, step)
            step += 1
        except Exception:
            pass

        out = self.recorder.finish_scene()
        await context.close()
        await browser.close()
        await pw.stop()

        return out

    async def record_irctc_search(self, scene_id: str, origin: str, dest: str, date: str):
        """Record an IRCTC train search demonstration."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError("Playwright not installed. Install with: pip install playwright")

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Start recording
        await self.recorder.start_scene(
            scene_id,
            {"site": "irctc", "job_type": "search", "task": {"origin": origin, "dest": dest, "date": date}}
        )

        step = 1

        # Step 1: Navigate to IRCTC
        await page.goto("https://www.irctc.co.in/nget/train-search", wait_until="networkidle", timeout=30000)
        await self.recorder.record_step(page, {"type": "navigate", "url": "https://www.irctc.co.in/nget/train-search"}, step)
        step += 1
        await asyncio.sleep(2)

        # Step 2: Input origin
        try:
            await page.fill("input[placeholder='From']", origin, timeout=10000)
            await self.recorder.record_step(page, {"type": "input", "selector": "input[placeholder='From']", "value": origin}, step)
            step += 1
            await asyncio.sleep(1)
        except Exception as e:
            print(f"  ⚠ origin field not found: {e}")

        # Step 3: Input destination
        try:
            await page.fill("input[placeholder='To']", dest, timeout=10000)
            await self.recorder.record_step(page, {"type": "input", "selector": "input[placeholder='To']", "value": dest}, step)
            step += 1
            await asyncio.sleep(1)
        except Exception as e:
            print(f"  ⚠ dest field not found: {e}")

        # Step 4: Input date
        try:
            date_input = page.locator("input[id*='journeyDate']")
            if await date_input.count() > 0:
                await date_input.fill(date, timeout=10000)
                await self.recorder.record_step(page, {"type": "input", "selector": "input[id*='journeyDate']", "value": date}, step)
                step += 1
                await asyncio.sleep(1)
        except Exception as e:
            print(f"  ⚠ date field not found: {e}")

        # Step 5: Click search
        try:
            search_btn = page.locator("button:has-text('Search Trains')")
            if await search_btn.count() > 0:
                await search_btn.click(timeout=10000)
                await self.recorder.record_step(page, {"type": "click", "selector": "button:has-text('Search Trains')"}, step)
                step += 1
                await asyncio.sleep(3)
        except Exception as e:
            print(f"  ⚠ search button not found: {e}")

        # Step 6: Wait for results
        try:
            await page.wait_for_selector("div[class*='train-list']", timeout=5000)
            await self.recorder.record_step(page, {"type": "wait", "selector": "div[class*='train-list']"}, step)
            step += 1
        except Exception:
            pass

        out = self.recorder.finish_scene()
        await context.close()
        await browser.close()
        await pw.stop()

        return out
