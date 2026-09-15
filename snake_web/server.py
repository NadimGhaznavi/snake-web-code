"""Periodic status publishing, or a single publishing pass with --once."""

import argparse
import logging
import os
import signal
import threading

from snake_web.activity.AppDb import AppDb
from snake_web.activity.PublishStatus import PublishStatus
from snake_web.constants.DSnakeWeb import DSnakeWeb
from snake_web.interface.DbMgr import DbMgr
from snake_web.interface.GitPublisher import GitPublisher


def publish_once() -> str:
    with DbMgr() as db:
        return PublishStatus(
            AppDb(db),
            GitPublisher(os.environ["PUBLISH_CHECKOUT"], os.environ.get("PUBLISH_BRANCH", "main")),
        ).run()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Publish once and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    interval = DSnakeWeb.POLL_INTERVAL
    if interval <= 0:
        parser.error("DSnakeWeb.POLL_INTERVAL must be positive")
    stopped = threading.Event()

    def stop(signum, frame):
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopped.is_set():
        try:
            logging.info(publish_once())
        except Exception as exc:
            logging.error("Status publishing failed: %s", exc)
            if args.once:
                return 1
        if args.once or stopped.wait(interval):
            break
    logging.info("Snake Web stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
