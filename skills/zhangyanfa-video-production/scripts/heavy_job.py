#!/usr/bin/env python3
"""One stable advisory lock for Foxjiu heavy jobs; never delete a live lock file."""
from contextlib import contextmanager
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess

DEFAULT_LOCK = Path.home()/'Documents/视频工作区/03_制作缓存/.foxjiu-heavy-worker.lock'
LEGACY_LOCK = Path.home()/'Documents/视频制作缓存/.foxjiu-heavy-worker.lock'


@contextmanager
def heavy_lock(path=None):
    if path is None and LEGACY_LOCK.exists():
        if not DEFAULT_LOCK.exists() or not os.path.samefile(LEGACY_LOCK,DEFAULT_LOCK):
            raise RuntimeError('legacy and canonical heavy-worker locks are not the same file; complete the storage migration before starting another worker')
    path = Path(path or DEFAULT_LOCK).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f'another heavy worker owns the shared lock: {path}') from exc
        handle.seek(0); handle.truncate()
        handle.write(json.dumps({'pid':os.getpid(),'scope':'one heavy process group'},ensure_ascii=False)+'\n'); handle.flush()
        # Children may inherit the descriptor so a killed parent cannot silently unlock a live worker.
        try:
            yield handle.fileno()
        finally:
            # close(), rather than LOCK_UN, preserves the lock if a child still owns the descriptor.
            pass


def run(command):
    with heavy_lock() as fd:
        process = subprocess.Popen(command, start_new_session=True, pass_fds=(fd,))
        old_handlers = {}
        def stop(signum, frame):
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait()
            raise SystemExit(128+signum)
        for signum in (signal.SIGTERM, signal.SIGINT):
            old_handlers[signum] = signal.signal(signum, stop)
        try: return process.wait()
        finally:
            for signum, handler in old_handlers.items(): signal.signal(signum, handler)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    command=args.command[1:] if args.command[:1]==['--'] else args.command
    if not command: parser.error('provide a command after --')
    try: return run(command)
    except RuntimeError as exc:
        print(str(exc)); return 75


if __name__=='__main__': raise SystemExit(main())
