"""
Minimal systemd sd_notify client — no external dependency.

Lets the app tell systemd it started successfully (READY=1) and, if the
unit sets WatchdogSec=, that it's still alive and not hung (WATCHDOG=1).
No-ops entirely when not run under systemd (NOTIFY_SOCKET unset), so
this is always safe to call, including in local/dev runs.
"""
import os
import socket
import threading
import time


def _send(msg: str) -> None:
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        sock.connect(addr)
        sock.sendall(msg.encode())
    except OSError as e:
        print("[sdnotify] failed to send:", e)
    finally:
        sock.close()


def ready() -> None:
    _send("READY=1")


def status(text: str) -> None:
    _send(f"STATUS={text}")


def start_watchdog_loop(is_healthy) -> None:
    """
    Ping the systemd watchdog on a timer, but only while `is_healthy()`
    returns True. If the app hangs or `is_healthy` starts returning
    False, we simply stop pinging — systemd's WatchdogSec then expires
    and it kills + restarts the unit, which a plain crash-only restart
    policy can't do for a wedged-but-alive process.
    """
    usec = os.environ.get("WATCHDOG_USEC")
    if not usec:
        return
    try:
        interval = max(1.0, int(usec) / 1_000_000 / 2)
    except ValueError:
        return

    def _loop():
        while True:
            try:
                if is_healthy():
                    _send("WATCHDOG=1")
                else:
                    print("[sdnotify] unhealthy — withholding watchdog ping.")
            except Exception as e:
                print("[sdnotify] health check raised:", e)
            time.sleep(interval)

    threading.Thread(target=_loop, daemon=True).start()
