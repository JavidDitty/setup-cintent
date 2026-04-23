#!/usr/bin/env python3
"""
Low-overhead deterministic profiler using sys.monitoring (PEP 669, Python 3.12+).

Key advantages over sys.setprofile:
  - C-level callback dispatch (no per-call Python frame setup overhead)
  - Returning DISABLE permanently removes callbacks for non-workspace code
    objects, so stdlib/library calls incur zero future cost after first sight
  - PY_START / PY_RETURN fire only for Python functions, skipping C calls

Falls back to an optimised sys.setprofile on Python < 3.12.

Injected into target processes via sitecustomize.py + PYTHONPATH (same
mechanism as the setprofile profiler).

Output CSV: timestamp_ns,thread_id,event,function,filename,line
"""

import sys
import os
import time
import atexit
import threading

# ── Configuration from environment ────────────────────────────────
step_id    = os.environ.get('CINTENT_STEP_ID', '0')
log_dir    = os.environ.get('CINTENT_LOGS', '/tmp')
_workspace = os.environ.get('GITHUB_WORKSPACE', '')
_max_calls = int(os.environ.get('CINTENT_MAX_CALLS', '10000000'))

_pid = os.getpid()
_ts  = int(time.time() * 1_000_000_000)
log_file = f"{log_dir}/{_ts}_{_pid}.{step_id}.sysmonitor.csv"

# 8 KB write-buffer — reduces syscall frequency without delaying data
_log = open(log_file, 'w', buffering=8192)
_log.write("timestamp_ns,thread_id,event,function,filename,line\n")

_call_count = 0
_is_shutting_down = False
_write_lock = threading.Lock()

# ── Workspace path prefixes ───────────────────────────────────────
# The profiler captures events only from files under these prefixes.
# GITHUB_WORKSPACE covers source files checked out in the repo.
# CINTENT_PROJECT_PATHS (set by the bash wrapper) covers the same project's
# packages when installed into site-packages via `pip install .`.
_ws_prefixes = []
if _workspace:
    _ws_prefixes.append(_workspace)
_extra = os.environ.get('CINTENT_PROJECT_PATHS', '')
if _extra:
    for p in _extra.split(os.pathsep):
        p = p.strip()
        if p and p not in _ws_prefixes:
            _ws_prefixes.append(p)

if len(_ws_prefixes) > 1:
    print(
        f"[sysmonitor] Workspace prefixes: {_ws_prefixes}",
        file=sys.stderr,
    )

# ── Workspace membership cache ────────────────────────────────────
# Avoids repeated string prefix checks on the hot path.
# NOTE: no PEP 585 type annotation here — must stay compatible with Python 3.8+
_ws_cache = {}
_ws_prefix_tuple = tuple(_ws_prefixes)  # tuple for fast startswith check


def _is_workspace(filename: str) -> bool:
    hit = _ws_cache.get(filename)
    if hit is not None:
        return hit
    result = bool(_ws_prefix_tuple) and filename.startswith(_ws_prefix_tuple)
    _ws_cache[filename] = result
    return result


# ── Cleanup ───────────────────────────────────────────────────────
def _cleanup() -> None:
    global _is_shutting_down
    _is_shutting_down = True
    threading.setprofile(None)
    sys.setprofile(None)
    if '_TOOL_ID' in globals() and hasattr(sys, 'monitoring'):
        try:
            sys.monitoring.set_events(_TOOL_ID, 0)
        except Exception:
            pass
    with _write_lock:
        _log.flush()
        _log.close()
    print(
        f"[sysmonitor] Captured {_call_count} events to {log_file}",
        file=sys.stderr,
    )


atexit.register(_cleanup)

# ── Choose backend ────────────────────────────────────────────────

if hasattr(sys, 'monitoring') and hasattr(sys.monitoring, 'PROFILER_ID'):
    # ╔══════════════════════════════════════════════════════════════╗
    # ║  sys.monitoring (PEP 669) — Python 3.12+                   ║
    # ╚══════════════════════════════════════════════════════════════╝
    DISABLE = sys.monitoring.DISABLE
    _TOOL_ID = sys.monitoring.PROFILER_ID

    try:
        sys.monitoring.use_tool_id(_TOOL_ID, "cintent")
    except ValueError:
        # PROFILER_ID already claimed; grab a free slot instead
        _TOOL_ID = sys.monitoring.free_tool_id()
        sys.monitoring.use_tool_id(_TOOL_ID, "cintent")

    # Bind once to avoid per-call attribute lookups
    _time_ns = time.time_ns
    _get_ident = threading.get_ident

    def _py_start(code, instruction_offset):
        """Called on every Python function entry."""
        global _call_count
        if _is_shutting_down:
            return DISABLE
        fn = code.co_filename
        if not _is_workspace(fn):
            return DISABLE            # permanently silence this code object
        with _write_lock:
            if _is_shutting_down:
                return DISABLE
            if _call_count >= _max_calls:
                return DISABLE
            _call_count += 1
            _log.write(
                f"{_time_ns()},{_get_ident()},call,{code.co_name},{fn},{code.co_firstlineno}\n"
            )

    def _py_return(code, instruction_offset, retval):
        """Called on every Python function return."""
        global _call_count
        if _is_shutting_down:
            return DISABLE
        fn = code.co_filename
        if not _is_workspace(fn):
            return DISABLE
        with _write_lock:
            if _is_shutting_down:
                return DISABLE
            if _call_count >= _max_calls:
                return DISABLE
            _call_count += 1
            _log.write(
                f"{_time_ns()},{_get_ident()},return,{code.co_name},{fn},{code.co_firstlineno}\n"
            )

    # Register callbacks and enable events
    sys.monitoring.register_callback(
        _TOOL_ID, sys.monitoring.events.PY_START, _py_start,
    )
    sys.monitoring.register_callback(
        _TOOL_ID, sys.monitoring.events.PY_RETURN, _py_return,
    )
    sys.monitoring.set_events(
        _TOOL_ID,
        sys.monitoring.events.PY_START | sys.monitoring.events.PY_RETURN,
    )

    print(
        f"[sysmonitor] sys.monitoring active (PEP 669), logging to {log_file}",
        file=sys.stderr,
    )
else:
    print(
        f"[sysmonitor] sys.monitoring is not available, logging is disabled (PEP 669)",
        file=sys.stderr,
    )

# else:
#     # ╔══════════════════════════════════════════════════════════════╗
#     # ║  Fallback: sys.setprofile — Python < 3.12                  ║
#     # ╚══════════════════════════════════════════════════════════════╝

#     def _profile_handler(frame, event, arg):
#         global _call_count
#         if _is_shutting_down:
#             return
#         if event not in ('call', 'return'):
#             return
#         filename = frame.f_code.co_filename
#         if 'sysmonitor_profiler' in filename:
#             return
#         if not _is_workspace(filename):
#             return
#         with _write_lock:
#             if _is_shutting_down:
#                 return
#             if _call_count >= _max_calls:
#                 return
#             _call_count += 1
#             _log.write(
#                 f"{time.time_ns()},{threading.get_ident()},{event},"
#                 f"{frame.f_code.co_name},{filename},{frame.f_code.co_firstlineno}\n"
#             )

#     # Install for current thread and all future threads so callback handlers
#     # executed by framework worker/event-loop threads are captured.
#     threading.setprofile(_profile_handler)
#     sys.setprofile(_profile_handler)
#     print(
#         f"[sysmonitor] sys.setprofile fallback active, logging to {log_file}",
#         file=sys.stderr,
#     )
