"""Convenience CLI wrapper so you can run:

python selector_registry.py --rollback <file>

This simply delegates to routemaster_agent.intelligence.selector_registry helpers.
"""
import sys
from pathlib import Path

from routemaster_agent.intelligence import selector_registry


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Selector registry CLI (wrapper)')
    parser.add_argument('--list-backups', action='store_true')
    parser.add_argument('--cleanup', action='store_true')
    parser.add_argument('--keep-last', type=int, default=50)
    parser.add_argument('--keep-days', type=int, default=14)
    parser.add_argument('--rollback', type=str)
    args = parser.parse_args(argv)

    if args.list_backups:
        for p in selector_registry._find_backup_files():
            print(p)
        return 0

    if args.cleanup:
        removed = selector_registry.cleanup_backups(keep_last=args.keep_last, keep_days=args.keep_days)
        for p in removed:
            print('removed', p)
        return 0

    if args.rollback:
        try:
            path = selector_registry.rollback_to_backup(args.rollback)
            print('rolled back to', path)
            return 0
        except Exception as e:
            print('rollback failed:', e)
            return 2

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))