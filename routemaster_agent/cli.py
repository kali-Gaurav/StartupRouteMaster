import argparse
import asyncio
from routemaster_agent.testing.runner import TestRunner


async def _run(args):
    trains = []
    if args.batch:
        # read first N train numbers from trains_master in DB? For now accept file or sample list
        # If a CSV is provided, load it. else use example static list.
        trains = [str(x).strip() for x in args.batch.split(',') if x.strip()]
    else:
        trains = args.trains or ["11603", "12345", "12951", "15640"]

    runner = TestRunner(
        train_numbers=trains,
        concurrency=args.concurrency,
        strict=args.strict,
        max_attempts=args.max_attempts,
    )
    res = await runner.run()
    print(res)


def main():
    parser = argparse.ArgumentParser(prog='rma-test', description='RouteMaster Agent QA Test Runner')
    sub = parser.add_subparsers(dest='cmd')

    runp = sub.add_parser('run')
    runp.add_argument('--batch', type=str, help='Comma-separated train numbers or path to file')
    runp.add_argument('--trains', nargs='+', help='List of train numbers')
    runp.add_argument('--concurrency', type=int, default=3)
    runp.add_argument('--strict', action='store_true')
    runp.add_argument('--max-attempts', type=int, default=5)

    args = parser.parse_args()
    if args.cmd == 'run':
        asyncio.run(_run(args))
    else:
        parser.print_help()


if __name__ == '__main__':
    main()