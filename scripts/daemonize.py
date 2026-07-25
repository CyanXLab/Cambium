#!/usr/bin/env python3
"""Daemonize a command: double-fork so the process becomes a child of init."""
import os
import sys

def daemonize_and_exec(cmd, cwd):
    # First fork
    pid = os.fork()
    if pid > 0:
        # Parent exits immediately
        print(f"Spawned child PID {pid}")
        sys.exit(0)
    # Child: become session leader
    os.setsid()
    # Second fork (so we can never acquire a controlling terminal)
    pid = os.fork()
    if pid > 0:
        os._exit(0)
    # Grandchild: this is the daemon
    os.chdir(cwd)
    os.umask(0)
    # Redirect stdio
    sys.stdout.flush()
    sys.stderr.flush()
    log_fd = os.open("/tmp/ai-chat.log", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    os.dup2(log_fd, 1)
    os.dup2(log_fd, 2)
    null_fd = os.open("/dev/null", os.O_RDONLY)
    os.dup2(null_fd, 0)
    os.close(log_fd)
    os.close(null_fd)
    # Exec the target
    os.execvp(cmd[0], cmd)

if __name__ == "__main__":
    # First arg = cwd, rest = command
    cwd = sys.argv[1]
    cmd = sys.argv[2:]
    daemonize_and_exec(cmd, cwd)
