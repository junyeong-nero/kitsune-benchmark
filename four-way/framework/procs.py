"""Process groups and virtualenv paths that work on macOS, Linux and Windows."""
import os
from pathlib import Path
import signal
import subprocess

WINDOWS = os.name == 'nt'
# Popen keyword arguments: a separate group, so kill_tree() also reaches MCP servers and browsers the child started.
GROUP = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {'start_new_session': True}


def kill_tree(proc, sig=signal.SIGKILL if hasattr(signal, 'SIGKILL') else None):
    """Kill proc and its descendants (POSIX: its session's process group; Windows: its live process tree)."""
    if WINDOWS:
        # taskkill follows parent links from a live PID. An exited parent's PID may already belong to another process.
        if proc.poll() is None:
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
        return
    try:
        os.killpg(proc.pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def venv_exe(venv, name):
    """An executable in a virtualenv: bin/<name> on POSIX, Scripts\\<name>.exe on Windows."""
    return Path(venv) / ('Scripts' if WINDOWS else 'bin') / (name + '.exe' if WINDOWS else name)
