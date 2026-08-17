"""Process-level safety guard for Kitty tests.

Python imports ``sitecustomize`` automatically when this checkout is on
``sys.path``. The guard is inert in production and activates only when
``KITTY_TEST_GUARD=1``. Pytest also calls :func:`install_test_guards` directly
so the parent test process is protected before test modules are collected.
"""
from __future__ import annotations

import builtins
import io
import ipaddress
import os
import shutil
import socket
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CANONICAL_DATA = (ROOT / "data").resolve()

_INSTALLED = False
_EXTERNAL_CONNECTS = 0


def _enabled() -> bool:
    return os.environ.get("KITTY_TEST_GUARD") == "1"


def _controlled_live() -> bool:
    return (
        os.environ.get("KITTY_TEST_CONTROLLED_LIVE_ACTIVE") == "1"
        and os.environ.get("KITTY_TEST_ALLOW_LIVE") == "1"
        and os.environ.get("KITTY_TEST_CHARGE_OK") == "1"
    )


def _is_loopback(host: Any) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="ignore")
    text = str(host).strip().lower()
    if text == "localhost" or text.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


def _path(value: Any) -> Path | None:
    if isinstance(value, int) or value is None:
        return None
    try:
        text = os.fspath(value)
    except TypeError:
        return None
    if isinstance(text, bytes):
        text = os.fsdecode(text)
    if text == ":memory:" or str(text).startswith("file::memory:"):
        return None
    if str(text).startswith("file:"):
        text = str(text)[5:].split("?", 1)[0]
    try:
        return Path(text).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return None


def _canonical(value: Any) -> bool:
    path = _path(value)
    return path is not None and (path == CANONICAL_DATA or CANONICAL_DATA in path.parents)


def _deny_path(value: Any, operation: str) -> None:
    if _enabled() and _canonical(value):
        raise RuntimeError(
            f"canonical Kitty runtime mutation blocked during tests: {operation} {value!r}"
        )


def _deny_external(host: Any) -> None:
    global _EXTERNAL_CONNECTS
    if not _enabled() or _is_loopback(host):
        return
    if not _controlled_live():
        raise RuntimeError(
            f"external network disabled for tests: {host!r}; use loopback/mock transport "
            "or an explicitly authorized controlled_live test"
        )
    cap = int(os.environ.get("KITTY_TEST_LIVE_MAX_REQUESTS", "1"))
    _EXTERNAL_CONNECTS += 1
    if _EXTERNAL_CONNECTS > cap:
        raise RuntimeError(f"controlled_live external connection cap exceeded: {cap}")


def reset_live_counter() -> None:
    global _EXTERNAL_CONNECTS
    _EXTERNAL_CONNECTS = 0


def install_test_guards() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    real_open = builtins.open
    real_io_open = io.open
    real_os_open = os.open
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_sendto = socket.socket.sendto
    real_getaddrinfo = socket.getaddrinfo
    real_sqlite_connect = sqlite3.connect

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            _deny_path(file, f"open({mode})")
        return real_open(file, mode, *args, **kwargs)

    def guarded_io_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            _deny_path(file, f"io.open({mode})")
        return real_io_open(file, mode, *args, **kwargs)

    def guarded_os_open(path, flags, *args, **kwargs):
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
        if flags & write_flags:
            _deny_path(path, "os.open")
        return real_os_open(path, flags, *args, **kwargs)

    def guarded_sqlite(database, *args, **kwargs):
        _deny_path(database, "sqlite3.connect")
        return real_sqlite_connect(database, *args, **kwargs)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if _enabled() and not _is_loopback(host) and not _controlled_live():
            _deny_external(host)
        return real_getaddrinfo(host, *args, **kwargs)

    def guarded_connect(sock, address):
        if sock.family != socket.AF_UNIX:
            host = address[0] if isinstance(address, tuple) and address else address
            _deny_external(host)
        return real_connect(sock, address)

    def guarded_connect_ex(sock, address):
        if sock.family != socket.AF_UNIX:
            host = address[0] if isinstance(address, tuple) and address else address
            _deny_external(host)
        return real_connect_ex(sock, address)

    def guarded_sendto(sock, data, *args):
        if sock.family != socket.AF_UNIX:
            address = args[-1] if args else None
            host = address[0] if isinstance(address, tuple) and address else address
            _deny_external(host)
        return real_sendto(sock, data, *args)

    builtins.open = guarded_open
    io.open = guarded_io_open
    os.open = guarded_os_open
    sqlite3.connect = guarded_sqlite
    socket.getaddrinfo = guarded_getaddrinfo
    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = guarded_connect_ex  # type: ignore[method-assign]
    socket.socket.sendto = guarded_sendto  # type: ignore[method-assign]

    def wrap_one(name: str) -> None:
        real = getattr(os, name)
        def guarded(path, *args, **kwargs):
            _deny_path(path, f"os.{name}")
            return real(path, *args, **kwargs)
        setattr(os, name, guarded)

    for name in ("mkdir", "makedirs", "remove", "unlink", "rmdir", "chmod", "chown"):
        if hasattr(os, name):
            wrap_one(name)

    for name in ("rename", "replace", "link", "symlink"):
        if not hasattr(os, name):
            continue
        real = getattr(os, name)
        def guarded_pair(src, dst, *args, __real=real, __name=name, **kwargs):
            _deny_path(src, f"os.{__name} source")
            _deny_path(dst, f"os.{__name} destination")
            return __real(src, dst, *args, **kwargs)
        setattr(os, name, guarded_pair)

    real_rmtree = shutil.rmtree
    def guarded_rmtree(path, *args, **kwargs):
        _deny_path(path, "shutil.rmtree")
        return real_rmtree(path, *args, **kwargs)
    shutil.rmtree = guarded_rmtree  # type: ignore[assignment]


if _enabled():
    install_test_guards()
