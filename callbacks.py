"""
callbacks.py
-------------
Central registry for Modbus task callbacks.

This module provides:
- A global CALLBACK_REGISTRY that maps string names → Python callables.
- A @register_callback("name") decorator to register callbacks easily.
- Optional helper to auto-register all top-level functions.

Import this module in the  main app or Modbus worker to access the registry.
"""

from typing import Callable, Dict, Any

# ──────────────────────────────────────────────────────────────
# Global registry: callback name → function reference
# ──────────────────────────────────────────────────────────────
CALLBACK_REGISTRY: Dict[str, Callable[..., Any]] = {}


# ──────────────────────────────────────────────────────────────
# Decorator to register callback functions by name
# ──────────────────────────────────────────────────────────────
def register_callback(name: str):
    """
    Decorator to register a callback function under a given name.

    Usage:
        @register_callback("on_write_done")
        def on_write_done(value, timestamp, **kwargs):
            ...
    """
    def decorator(func: Callable[..., Any]):
        CALLBACK_REGISTRY[name] = func
        return func
    return decorator


# ──────────────────────────────────────────────────────────────
# Optional helper: auto-register all top-level functions
# ──────────────────────────────────────────────────────────────
def auto_register_callbacks(module_globals: Dict[str, Any]):
    """
    Automatically register all top-level functions in the caller module.
    Example use at bottom of a file:
        auto_register_callbacks(globals())
    """
    import inspect
    for name, obj in module_globals.items():
        if inspect.isfunction(obj):
            CALLBACK_REGISTRY[name] = obj


# ──────────────────────────────────────────────────────────────
# Example (optional): diagnostic helper
# ──────────────────────────────────────────────────────────────
def list_registered_callbacks() -> Dict[str, Callable]:
    """Return a dictionary of all registered callbacks."""
    return CALLBACK_REGISTRY.copy()

def get_callback_name(func) -> str | None:
    """
    Given a function reference, return its registered callback name.
    Returns None if not found.
    """
    for name, registered_func in CALLBACK_REGISTRY.items():
        if registered_func is func:
            return name
    return None