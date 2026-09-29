"""Limitador simple de intentos de login (fuerza bruta).

Guarda los intentos fallidos en memoria del proceso. Para despliegues con
varios workers conviene reemplazarlo por Redis (misma interfaz).
"""
import threading
import time

_lock = threading.Lock()
_attempts: dict[str, list[float]] = {}

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 15 * 60


def _prune(key: str, now: float) -> list[float]:
    recent = [t for t in _attempts.get(key, []) if now - t < WINDOW_SECONDS]
    if recent:
        _attempts[key] = recent
    else:
        _attempts.pop(key, None)
    return recent


def is_blocked(key: str) -> bool:
    with _lock:
        return len(_prune(key, time.time())) >= MAX_ATTEMPTS


def register_failure(key: str) -> None:
    with _lock:
        now = time.time()
        _prune(key, now)
        _attempts.setdefault(key, []).append(now)


def reset(key: str) -> None:
    with _lock:
        _attempts.pop(key, None)
