"""Network guard: inside Cairn, only connections to this computer are possible.

Installed at start in the app and in the speech process. Any attempt to reach another
address, or to resolve an outside name, is refused and counted. The only exception is an
action you trigger yourself (the update check), wrapped in `allow()`.
"""

import ipaddress
import socket
import threading
from contextlib import contextmanager

_local = threading.local()
_state = {"installed": False, "blocked": []}
_lock = threading.Lock()
LOCAL_NAMES = {"localhost", "localhost.localdomain", ""}


class NetworkBlocked(PermissionError):
    pass


def _is_local(host):
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "ignore")
    if host.lower() in LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _refuse(target):
    if getattr(_local, "allowed", 0):
        return
    with _lock:
        _state["blocked"].append(str(target)[:120])
    raise NetworkBlocked("Cairn blocks connections to outside addresses: %s" % (target,))


def _check_address(sock, address):
    if sock.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple) and not _is_local(address[0]):
        _refuse(address[0])


@contextmanager
def allow(reason=""):
    """Let the current thread reach the network for one action the user asked for."""
    _local.allowed = getattr(_local, "allowed", 0) + 1
    try:
        yield
    finally:
        _local.allowed -= 1


def install():
    if _state["installed"]:
        return
    _state["installed"] = True
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
    original_sendto, original_getaddrinfo = socket.socket.sendto, socket.getaddrinfo

    def connect(self, address):
        _check_address(self, address)
        return original_connect(self, address)

    def connect_ex(self, address):
        _check_address(self, address)
        return original_connect_ex(self, address)

    def sendto(self, data, *args):
        if args:
            _check_address(self, args[-1])
        return original_sendto(self, data, *args)

    def getaddrinfo(host, *args, **kwargs):
        if not _is_local(host):
            _refuse(host)
        return original_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto = connect, connect_ex, sendto
    socket.getaddrinfo = getaddrinfo


def blocked():
    with _lock:
        return list(_state["blocked"])
