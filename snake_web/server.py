"""Periodic status publishing, or a single publishing pass with --once."""

import argparse
from datetime import datetime, timedelta
import logging
import os
import signal
import threading

from snake_web.activity.AppDb import AppDb
from snake_web.activity.PublishStatus import PublishStatus
from snake_web.interface.DbMgr import DbMgr
from snake_web.interface.GitPublisher import GitPublisher


def publish_once() -> str:
    with DbMgr() as db:
        return PublishStatus(
            AppDb(db),
            GitPublisher(os.environ["PUBLISH_CHECKOUT"], os.environ.get("PUBLISH_BRANCH", "main")),
        ).run()


def seconds_until_next_publish(now: datetime) -> float:
    boundary = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0)
    return (boundary + timedelta(minutes=30) - now).total_seconds()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Publish once and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    stopped = threading.Event()

    def stop(signum, frame):
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopped.is_set():
        if not args.once and stopped.wait(seconds_until_next_publish(datetime.now())):
            break
        try:
            logging.info(publish_once())
        except Exception as exc:
            logging.error("Status publishing failed: %s", exc)
            if args.once:
                return 1
        if args.once:
            break
    logging.info("Snake Web stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
