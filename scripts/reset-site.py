#!/usr/bin/env python3
"""Clear published experiment data before moving Snake Web to a new source database."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snake_web.interface.GitPublisher import GitPublisher


EMPTY_HOME = '''---
title: Ax3l Experiment Status
author_profile: false
layout: single
classes: wide
---

# Current Experiment

Waiting for the first publication from the new experiment.
'''


def validate_site(publisher):
    """Require the dedicated site repository, with no work to accidentally discard."""
    top = Path(publisher._git('rev-parse', '--show-toplevel').stdout.strip()).resolve()
    if top != publisher.checkout:
        raise RuntimeError('Checkout must be the website repository root')
    if publisher._git('branch', '--show-current').stdout.strip() != publisher.branch:
        raise RuntimeError(f'Checkout must be on {publisher.branch}')
    if publisher._git('status', '--porcelain', '--untracked-files=all').stdout:
        raise RuntimeError('Checkout must be clean; commit or resolve existing changes first')
    config = publisher.checkout / '_config.yml'
    if config.resolve() != config or not config.is_file():
        raise RuntimeError('Expected a Jekyll website checkout with a regular _config.yml')
    publisher._git('ls-files', '--error-unmatch', '--', '_config.yml')
    publisher._status_file()
    # Validate every managed path before removing any file.
    for name in publisher.OWNED_PATHS:
        publisher._managed_file(name)


def reset_site(publisher, *, apply=False, push=False):
    if push and not apply:
        raise ValueError('--push requires --apply')
    validate_site(publisher)
    if not apply:
        print(f'Preview only: {publisher.checkout} ({publisher.branch})')
        print('Replace index.md with a fresh-experiment placeholder.')
        for name in publisher.OWNED_PATHS:
            if name != publisher.STATUS_PATH and (publisher.checkout / name).exists():
                print(f'Remove {name}')
        print('Keep Git history, site configuration, CNAME, pages, and all other files.')
        print('Use --apply to commit the reset; add --push to publish it.')
        return
    # Same lock and branch synchronization as the daemon; never force-push.
    with publisher.session():
        validate_site(publisher)
        changed = []
        for name in publisher.OWNED_PATHS:
            path = publisher._managed_file(name)
            if name == publisher.STATUS_PATH:
                if path.read_bytes() != EMPTY_HOME.encode('utf-8'):
                    publisher._write_file(path, EMPTY_HOME)
                    changed.append(name)
            elif path.exists():
                path.unlink()
                changed.append(name)
        if changed:
            publisher._git('add', '--all', '--', *changed)
            publisher._git('commit', '-m', 'Reset published experiment for a new source', '--', *changed)
            print('Reset committed locally.')
        else:
            print('Published experiment is already reset.')
        if push:
            publisher._git('push', 'origin', f'HEAD:refs/heads/{publisher.branch}')
            print('Reset pushed to origin.')
        else:
            print('Rerun with --apply --push when ready to publish the reset.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'Stop the daemon on the old machine before applying this reset. '
        'After pushing, sync the new machine’s publishing checkout before starting its daemon. '
        'Old data remains in Git history; this does not erase repository history or source databases.'))
    parser.add_argument('checkout', help='Dedicated snake-web website checkout (not snake-web-code)')
    parser.add_argument('--branch', default='main', help='Publishing branch (default: main)')
    parser.add_argument('--apply', action='store_true', help='Remove managed reports/data and commit the placeholder homepage')
    parser.add_argument('--push', action='store_true', help='Also push the reset commit; requires --apply')
    args = parser.parse_args()
    if args.push and not args.apply:
        parser.error('--push requires --apply')
    try:
        reset_site(GitPublisher(args.checkout, args.branch), apply=args.apply, push=args.push)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'Reset failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
