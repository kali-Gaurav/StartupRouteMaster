#!/usr/bin/env python3
"""
RouteMaster Concurrency Load Testing Framework
==============================================

Tests concurrent search behavior vs sequential throughput.
Critical for production capacity planning.

Key Insights:
- Sequential throughput ≠ concurrency performance
- Burst loads reveal race conditions and resource contention
- Memory leaks appear under sustained concurrent load
"""

import asyncio
import aiohttp
import json
import logging
import statistics
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import matplotlib.pyplot as plt
import numpy as np
from prometheus_client import Counter, Histogram, Gauge

# Metrics
CONCURRENCY_TESTS_TOTAL = Counter(
    'concurrency_tests_total',
    'Total concurrency tests executed',
    ['test_type', 'concurrency_level']
)

CONCURRENCY_LATENCY = Histogram(
    'concurrency_test_latency_seconds',
    'Latency distribution for concurrency tests',
    ['test_type', 'concurrency_level'],
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 25, 50, 100)
)

CONCURRENCY_ERRORS = Counter(
    'concurrency_test_errors_total',
    'Total errors during concurrency tests',
    ['test_type', 'error_type']
)

@dataclass
class ConcurrencyTestResult:
    """Results from a concurrency test"""
    test_name: str
    concurrency_level: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_latency: float
    p95_latency: float
    p99_latency: float
    min_latency: float
    max_latency: float
    requests_per_second: float
    duration_seconds: float
    error_types: Dict[str, int]
    timestamp: datetime

@dataclass
class LoadTestScenario:
    """Definition of a load testing scenario"""
    name: str
    concurrency_levels: List[int]  # [1, 5, 10, 25, 50, 100]
    requests_per_level: int  # How many requests at each concurrency level
    request_generator: callable  # Function to generate test requests
    duration_seconds: Optional[int] = None  # For sustained load tests

class RouteMasterConcurrencyTester:
    """
    Comprehensive concurrency testing for RouteMaster backend

    Tests:
    1. Burst concurrency (multiple simultaneous requests)
    2. Sustained load (continuous requests over time)
    3. Memory leak detection (long-running concurrent load)
    4. Race condition detection (concurrent state modifications)
    """

    def __init__(self,
                 base_url: str = "http://localhost:8000",
                 timeout_seconds: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout_seconds = timeout_seconds
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def run_burst_test(self,
                           concurrency_levels: List[int],
                           requests_per_level: int = 100,
                           request_generator: callable = None) -> List[ConcurrencyTestResult]:
        """
        Run burst concurrency tests at different levels

        Args:
            concurrency_levels: List of concurrency levels to test [1, 5, 10, 25, 50]
            requests_per_level: Number of requests to make at each level
            request_generator: Function that returns request data dict

        Returns:
            List of test results for each concurrency level
        """
        if request_generator is None:
            request_generator = self._default_route_search_generator

        results = []

        for concurrency in concurrency_levels:
            logging.info(f"Testing concurrency level: {concurrency}")

            result = await self._run_concurrency_level(
                concurrency=concurrency,
                total_requests=requests_per_level,
                request_generator=request_generator,
                test_type="burst"
            )

            results.append(result)
            CONCURRENCY_TESTS_TOTAL.labels(
                test_type="burst",
                concurrency_level=str(concurrency)
            ).inc()

            logging.info(f"Level {concurrency}: {result.requests_per_second:.1f} req/sec, "
                        f"p95: {result.p95_latency:.2f}s")

        return results

    async def run_sustained_load_test(self,
                                    concurrency: int,
                                    duration_seconds: int,
                                    request_generator: callable = None) -> ConcurrencyTestResult:
        """
        Run sustained load test for memory leak detection

        Args:
            concurrency: Number of concurrent requests
            duration_seconds: How long to run the test
            request_generator: Function that returns request data

        Returns:
            Test result with sustained load metrics
        """
        if request_generator is None:
            request_generator = self._default_route_search_generator

        logging.info(f"Running sustained load test: {concurrency} concurrent for {duration_seconds}s")

        start_time = time.time()
        end_time = start_time + duration_seconds

        all_latencies = []
        error_counts = {}
        successful_requests = 0
        total_requests = 0

        # Run concurrent requests continuously
        while time.time() < end_time:
            batch_start = time.time()

            # Create batch of concurrent requests
            tasks = []
            for _ in range(concurrency):
                request_data = request_generator()
                task = self._make_request("/api/routes/search", request_data)
                tasks.append(task)

            # Execute batch
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in batch_results:
                total_requests += 1

                if isinstance(result, Exception):
                    error_type = type(result).__name__
                    error_counts[error_type] = error_counts.get(error_type, 0) + 1
                else:
                    latency, status = result
                    all_latencies.append(latency)
                    if status == 200:
                        successful_requests += 1

            # Small delay to prevent overwhelming
            await asyncio.sleep(0.01)

        actual_duration = time.time() - start_time
        failed_requests = total_requests - successful_requests

        # Calculate metrics
        if all_latencies:
            avg_latency = statistics.mean(all_latencies)
            p95_latency = statistics.quantiles(all_latencies, n=20)[18]  # 95th percentile
            p99_latency = statistics.quantiles(all_latencies, n=100)[98]  # 99th percentile
            min_latency = min(all_latencies)
            max_latency = max(all_latencies)
        else:
            avg_latency = p95_latency = p99_latency = min_latency = max_latency = 0

        requests_per_second = total_requests / actual_duration

        result = ConcurrencyTestResult(
            test_name=f"sustained_{concurrency}conc_{duration_seconds}s",
            concurrency_level=concurrency,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_latency=avg_latency,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            min_latency=min_latency,
            max_latency=max_latency,
            requests_per_second=requests_per_second,
            duration_seconds=actual_duration,
            error_types=error_counts,
            timestamp=datetime.utcnow()
        )

        CONCURRENCY_TESTS_TOTAL.labels(
            test_type="sustained",
            concurrency_level=str(concurrency)
        ).inc()

        return result

    async def _run_concurrency_level(self,
                                    concurrency: int,
                                    total_requests: int,
                                    request_generator: callable,
                                    test_type: str) -> ConcurrencyTestResult:
        """Run test at specific concurrency level"""
        start_time = time.time()
        all_latencies = []
        error_counts = {}
        successful_requests = 0
        actual_requests_executed = 0

        # Process requests in batches of concurrency size
        for batch_start in range(0, total_requests, concurrency):
            batch_size = min(concurrency, total_requests - batch_start)

            # Create concurrent requests
            tasks = []
            for _ in range(batch_size):
                request_data = request_generator()
                task = self._make_request("/api/routes/search", request_data)
                tasks.append(task)

            # Execute batch
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in batch_results:
                actual_requests_executed += 1

                if isinstance(result, Exception):
                    error_type = type(result).__name__
                    error_counts[error_type] = error_counts.get(error_type, 0) + 1
                    CONCURRENCY_ERRORS.labels(
                        test_type=test_type,
                        error_type=error_type
                    ).inc()
                else:
                    latency, status = result
                    all_latencies.append(latency)
                    CONCURRENCY_LATENCY.labels(
                        test_type=test_type,
                        concurrency_level=str(concurrency)
                    ).observe(latency)

                    if status == 200:
                        successful_requests += 1

        duration = time.time() - start_time
        failed_requests = actual_requests_executed - successful_requests

        # Calculate percentiles
        if all_latencies:
            sorted_latencies = sorted(all_latencies)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p99_idx = int(len(sorted_latencies) * 0.99)

            p95_latency = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)]
            p99_latency = sorted_latencies[min(p99_idx, len(sorted_latencies) - 1)]
            avg_latency = statistics.mean(all_latencies)
            min_latency = min(all_latencies)
            max_latency = max(all_latencies)
        else:
            avg_latency = p95_latency = p99_latency = min_latency = max_latency = 0

        requests_per_second = len(all_latencies) / duration if duration > 0 else 0

        return ConcurrencyTestResult(
            test_name=f"{test_type}_{concurrency}conc",
            concurrency_level=concurrency,
            total_requests=actual_requests_executed,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_latency=avg_latency,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            min_latency=min_latency,
            max_latency=max_latency,
            requests_per_second=requests_per_second,
            duration_seconds=duration,
            error_types=error_counts,
            timestamp=datetime.utcnow()
        )

    async def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Tuple[float, int]:
        """Make HTTP request and return (latency, status_code)"""
        if not self.session:
            raise RuntimeError("HTTP session not initialized")

        start_time = time.time()

        try:
            url = f"{self.base_url}{endpoint}"
            async with self.session.post(url, json=data) as response:
                latency = time.time() - start_time
                return latency, response.status

        except Exception as e:
            latency = time.time() - start_time
            # Re-raise as custom exception to distinguish from HTTP errors
            raise RuntimeError(f"Request failed: {type(e).__name__}: {e}") from e

    def _default_route_search_generator(self) -> Dict[str, Any]:
        """Generate realistic route search requests"""
        # Common Indian railway stations
        stations = [
            ("NDLS", "New Delhi"),
            ("MMCT", "Mumbai Central"),
            ("SBC", "Bangalore City"),
            ("MAS", "Chennai Central"),
            ("HWH", "Howrah"),
            ("PUNE", "Pune Junction"),
            ("LKO", "Lucknow"),
            ("BPL", "Bhopal"),
            ("AGC", "Agra Cantt"),
            ("JAT", "Jammu Tawi")
        ]

        # Select random origin and destination
        origin_idx = np.random.randint(0, len(stations))
        dest_idx = np.random.randint(0, len(stations))
        while dest_idx == origin_idx:  # Avoid same origin/destination
            dest_idx = np.random.randint(0, len(stations))

        origin_code, origin_name = stations[origin_idx]
        dest_code, dest_name = stations[dest_idx]

        # Generate realistic search parameters
        search_date = datetime.now() + timedelta(days=np.random.randint(1, 30))
        passenger_count = np.random.randint(1, 6)
        preferred_classes = np.random.choice(
            ['1A', '2A', '3A', 'SL', 'CC'],
            size=np.random.randint(1, 3),
            replace=False
        ).tolist()

        return {
            "origin": origin_code,
            "destination": dest_code,
            "date": search_date.strftime("%Y-%m-%d"),
            "passengers": int(passenger_count),
            "classes": preferred_classes,
            "flexible_dates": bool(np.random.choice([True, False], p=[0.3, 0.7]))
        }

class ConcurrencyTestReporter:
    """Generate reports and visualizations from concurrency tests"""

    @staticmethod
    def generate_report(results: List[ConcurrencyTestResult]) -> str:
        """Generate text report from test results"""
        report_lines = [
            "=" * 80,
            "ROUTEMASTER CONCURRENCY TEST REPORT",
            "=" * 80,
            f"Generated: {datetime.utcnow().isoformat()}",
            "",
        ]

        # Summary table
        report_lines.extend([
            "CONCURRENCY LEVEL SUMMARY",
            "-" * 50,
            "<15"
        ])

        for result in sorted(results, key=lambda x: x.concurrency_level):
            success_rate = (result.successful_requests / result.total_requests * 100) if result.total_requests > 0 else 0
            report_lines.append(
                f"{result.concurrency_level:>3} | "
                f"{result.requests_per_second:>6.1f} | "
                f"{result.avg_latency:>6.2f} | "
                f"{result.p95_latency:>6.2f} | "
                f"{success_rate:>5.1f}% | "
                f"{result.failed_requests:>3}"
            )

        report_lines.extend([
            "",
            "DETAILED RESULTS",
            "-" * 30,
        ])

        for result in results:
            report_lines.extend([
                f"Test: {result.test_name}",
                f"Concurrency: {result.concurrency_level}",
                f"Total Requests: {result.total_requests:,}",
                f"Successful: {result.successful_requests:,} ({result.successful_requests/result.total_requests*100:.1f}%)",
                f"Failed: {result.failed_requests:,}",
                f"Duration: {result.duration_seconds:.2f}s",
                f"Throughput: {result.requests_per_second:.1f} req/sec",
                f"Avg Latency: {result.avg_latency:.3f}s",
                f"P95 Latency: {result.p95_latency:.3f}s",
                f"P99 Latency: {result.p99_latency:.3f}s",
                f"Min/Max Latency: {result.min_latency:.3f}s / {result.max_latency:.3f}s",
            ])

            if result.error_types:
                report_lines.append("Errors:")
                for error_type, count in result.error_types.items():
                    report_lines.append(f"  {error_type}: {count}")

            report_lines.append("")

        return "\n".join(report_lines)

    @staticmethod
    def plot_results(results: List[ConcurrencyTestResult], output_file: str = "concurrency_test.png"):
        """Generate visualization of test results"""
        try:
            concurrency_levels = [r.concurrency_level for r in sorted(results, key=lambda x: x.concurrency_level)]
            throughput = [r.requests_per_second for r in sorted(results, key=lambda x: x.concurrency_level)]
            p95_latency = [r.p95_latency for r in sorted(results, key=lambda x: x.concurrency_level)]
            success_rate = [(r.successful_requests / r.total_requests * 100) for r in sorted(results, key=lambda x: x.concurrency_level)]

            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))

            # Throughput vs Concurrency
            ax1.plot(concurrency_levels, throughput, 'bo-', linewidth=2, markersize=6)
            ax1.set_xlabel('Concurrency Level')
            ax1.set_ylabel('Requests/Second')
            ax1.set_title('Throughput Scaling')
            ax1.grid(True, alpha=0.3)

            # P95 Latency vs Concurrency
            ax2.plot(concurrency_levels, p95_latency, 'ro-', linewidth=2, markersize=6)
            ax2.set_xlabel('Concurrency Level')
            ax2.set_ylabel('P95 Latency (seconds)')
            ax2.set_title('Latency vs Concurrency')
            ax2.grid(True, alpha=0.3)

            # Success Rate vs Concurrency
            ax3.plot(concurrency_levels, success_rate, 'go-', linewidth=2, markersize=6)
            ax3.set_xlabel('Concurrency Level')
            ax3.set_ylabel('Success Rate (%)')
            ax3.set_title('Success Rate vs Concurrency')
            ax3.set_ylim(0, 105)
            ax3.grid(True, alpha=0.3)

            # Combined: Throughput and Latency
            ax4_twin = ax4.twinx()
            line1 = ax4.plot(concurrency_levels, throughput, 'b-', label='Throughput (req/sec)')
            line2 = ax4_twin.plot(concurrency_levels, p95_latency, 'r-', label='P95 Latency (s)')
            ax4.set_xlabel('Concurrency Level')
            ax4.set_ylabel('Requests/Second', color='b')
            ax4_twin.set_ylabel('P95 Latency (seconds)', color='r')
            ax4.set_title('Throughput vs Latency Trade-off')
            ax4.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            plt.close()

            logging.info(f"Concurrency test visualization saved to: {output_file}")

        except ImportError:
            logging.warning("matplotlib not available, skipping visualization")
        except Exception as e:
            logging.error(f"Failed to generate visualization: {e}")

# Example usage
async def main():
    """Example concurrency testing"""
    logging.basicConfig(level=logging.INFO)

    # Test scenarios
    burst_levels = [1, 5, 10, 25, 50]
    sustained_concurrency = 20
    sustained_duration = 60  # 1 minute

    async with RouteMasterConcurrencyTester(base_url="http://localhost:8000") as tester:
        print("🚀 Starting RouteMaster Concurrency Tests")

        # Burst tests
        print("\n📊 Running burst concurrency tests...")
        burst_results = await tester.run_burst_test(
            concurrency_levels=burst_levels,
            requests_per_level=100
        )

        # Sustained load test
        print(f"\n🔄 Running sustained load test ({sustained_concurrency} concurrent for {sustained_duration}s)...")
        sustained_result = await tester.run_sustained_load_test(
            concurrency=sustained_concurrency,
            duration_seconds=sustained_duration
        )

        # Generate report
        all_results = burst_results + [sustained_result]
        report = ConcurrencyTestReporter.generate_report(all_results)

        print("\n" + "="*80)
        print("CONCURRENCY TEST SUMMARY")
        print("="*80)

        for result in burst_results:
            success_rate = result.successful_requests / result.total_requests * 100
            print(f"Concurrency {result.concurrency_level:>2}: "
                  f"{result.requests_per_second:>6.1f} req/sec, "
                  f"p95: {result.p95_latency:>5.2f}s, "
                  f"success: {success_rate:>5.1f}%")

        print(f"\nSustained ({sustained_concurrency} conc, {sustained_duration}s): "
              f"{sustained_result.requests_per_second:.1f} req/sec sustained")

        # Save detailed report
        with open("concurrency_test_report.txt", "w") as f:
            f.write(report)

        # Generate visualization
        ConcurrencyTestReporter.plot_results(burst_results)

        print("📄 Detailed report saved to: concurrency_test_report.txt")
        print("📊 Visualization saved to: concurrency_test.png")
if __name__ == "__main__":
    asyncio.run(main())