#!/usr/bin/env python3
"""Provision Snake Web's dedicated reader using local MariaDB root access."""

import fcntl
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import tempfile

import pymysql


CREDENTIALS = Path('/etc/snake-web/database.env')
LEGACY_CREDENTIALS = Path('/etc/snake-lab/database.env')
MARKER = '# Managed by snake-web: dedicated read-only database account'
DB_USER = 'snake_web_reader'
DB_NAME = 'snakelab'


def load_credentials(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise RuntimeError('Database environment must be an owner-only regular file (0600)')
    lines = path.read_text().splitlines()
    if not lines or lines[0] != MARKER:
        raise RuntimeError('Existing database.env is not managed by Snake Web; it was left untouched')
    values = {}
    for line in lines[1:]:
        key, separator, value = line.partition('=')
        if not separator or key in values:
            raise RuntimeError('Invalid Snake Web database environment')
        values[key] = value
    expected = {'DB_HOST', 'DB_SOCKET', 'DB_NAME', 'DB_USER', 'DB_PASSWORD'}
    if (set(values) != expected or values['DB_HOST'] != 'localhost'
            or values['DB_NAME'] != DB_NAME or values['DB_USER'] != DB_USER
            or not re.fullmatch('[0-9a-f]{64}', values['DB_PASSWORD'])
            or not re.fullmatch(r'/[A-Za-z0-9_./-]+', values['DB_SOCKET'])):
        raise RuntimeError('Invalid Snake Web database environment')
    return values


def provision(admin, socket_path, credentials=CREDENTIALS, legacy_credentials=None):
    """The caller supplies an admin connection; source application data is never changed."""
    credentials = Path(credentials)
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', socket_path):
        raise RuntimeError('Unsupported MariaDB socket path')
    # Do not traverse symlinks or change an existing shared directory's permissions.
    for parent in credentials.parents:
        if parent.is_symlink():
            raise RuntimeError('Database configuration directory must not be a symlink')
    credentials.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = credentials.parent / '.snake-web-database.lock'
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with admin.cursor() as cursor:
            # Require the source schema to exist; never install Snake Lab's schema here.
            cursor.execute('SELECT high_score FROM snakelab.simulation_runs LIMIT 0')
            cursor.execute('SELECT COUNT(*) FROM mysql.user WHERE User=%s AND Host=%s', (DB_USER, 'localhost'))
            account_exists = cursor.fetchone()[0] != 0
            if credentials.exists() or credentials.is_symlink():
                values = load_credentials(credentials)
                if values['DB_SOCKET'] != socket_path:
                    raise RuntimeError('Saved socket differs from local MariaDB; credentials left unchanged')
            else:
                legacy = Path(legacy_credentials) if legacy_credentials is not None else None
                if legacy is not None and (legacy.exists() or legacy.is_symlink()):
                    if any(parent.is_symlink() for parent in legacy.parents):
                        raise RuntimeError('Legacy database configuration directory must not be a symlink')
                    values = load_credentials(legacy)
                    if values['DB_SOCKET'] != socket_path:
                        raise RuntimeError('Saved socket differs from local MariaDB; credentials left unchanged')
                else:
                    if account_exists:
                        raise RuntimeError('Reader account already exists without a managed credential file; left untouched')
                    values = dict(DB_HOST='localhost', DB_SOCKET=socket_path, DB_NAME=DB_NAME,
                                  DB_USER=DB_USER, DB_PASSWORD=secrets.token_hex(32))
                # Save first so an interrupted DB operation can reuse the same password.
                with tempfile.NamedTemporaryFile(mode='w', dir=credentials.parent) as stream:
                    stream.write(MARKER + '\n')
                    stream.writelines(f'{key}={value}\n' for key, value in values.items())
                    stream.flush()
                    os.fsync(stream.fileno())
                    # Publish a complete 0600 file, without replacing an existing path.
                    os.link(stream.name, credentials)
            cursor.execute('CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s',
                           (DB_USER, 'localhost', values['DB_PASSWORD']))
            cursor.execute('ALTER USER %s@%s IDENTIFIED BY %s',
                           (DB_USER, 'localhost', values['DB_PASSWORD']))
            cursor.execute('REVOKE ALL PRIVILEGES, GRANT OPTION FROM %s@%s', (DB_USER, 'localhost'))
            cursor.execute('GRANT SELECT ON snakelab.simulation_runs TO %s@%s', (DB_USER, 'localhost'))
        with pymysql.connect(unix_socket=socket_path, user=DB_USER, password=values['DB_PASSWORD'],
                             database=DB_NAME, connect_timeout=10) as reader:
            with reader.cursor() as cursor:
                cursor.execute('SELECT MAX(high_score) FROM simulation_runs')
                cursor.fetchone()


def main():
    if os.geteuid() != 0:
        print('Run database provisioning as root.', file=sys.stderr)
        return 1
    try:
        result = subprocess.run(
            ['mariadb', '--protocol=socket', '--user=root', '--batch', '--skip-column-names',
             '--execute=SELECT @@socket'],
            check=True, capture_output=True, text=True, timeout=30,
        )
        socket_path = result.stdout.strip()
        with pymysql.connect(unix_socket=socket_path, user='root', autocommit=True,
                             connect_timeout=10, read_timeout=30, write_timeout=30) as admin:
            provision(admin, socket_path, legacy_credentials=LEGACY_CREDENTIALS)
    except pymysql.MySQLError as exc:
        print(f'Database provisioning failed (MariaDB error {exc.args[0]}). Check local root access and Snake Lab schema.', file=sys.stderr)
        return 1
    except subprocess.SubprocessError:
        print('Cannot discover local MariaDB socket. Check mariadb client and local root access.', file=sys.stderr)
        return 1
    except (OSError, RuntimeError) as exc:
        print(f'Database provisioning failed: {exc}', file=sys.stderr)
        return 1
    print(f'Snake Web reader provisioned; credentials preserved at {CREDENTIALS}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
