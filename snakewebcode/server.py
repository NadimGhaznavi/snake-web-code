"""Refresh public GIFs on the hour and half hour, or immediately with --once."""

import argparse
from datetime import datetime, timedelta
import logging
import os
import signal
import threading

import pymysql
import zmq

from snakewebcode.activity.AppDb import AppDb
from snakewebcode.activity.PublishLive import PublishLive
from snakewebcode.interface.DbMgr import DbMgr
from snakewebcode.interface.StaticPublisher import StaticPublisher


def publish_once(*, collect_progress=True) -> str:
    with DbMgr() as db:
        return PublishLive(
            AppDb(db),
            StaticPublisher(os.environ.get('PUBLISH_DIRECTORY', '/var/lib/snake-web/public')),
        ).run(collect_progress=collect_progress)


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
            logging.info(publish_once(collect_progress=not args.once))
        except (OSError, RuntimeError, ValueError, pymysql.MySQLError, zmq.ZMQError) as exc:
            logging.error("Static publication failed: %s", exc)
            if args.once:
                return 1
        if args.once:
            break
    logging.info("Snake Web stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
