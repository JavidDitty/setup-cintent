#!/usr/bin/env python3
"""
Profile script using sys.setprofile() for deterministic 100% coverage profiling.
This is injected into the target Python process to capture all function calls.
"""

import sys
import os
import time
import atexit

# Get configuration from environment
step_id  = os.environ.get('CINTENT_STEP_ID', '0')
log_dir  = os.environ.get('CINTENT_LOGS', '/tmp')

# Workspace prefix filter – only log calls from files inside the GitHub
# Actions workspace.  This keeps files small and avoids exhausting the call
# limit on pytest/stdlib imports before repo code ever runs.
# GITHUB_WORKSPACE is always set on Actions runners, e.g.
#   /home/runner/work/graph-012/graph-012
_workspace = os.environ.get('GITHUB_WORKSPACE', '')

# Always generate a per-process unique log file using nanosecond timestamp +
# PID.  Multiple Python processes run concurrently during a test suite (pytest
# workers, subprocess calls, etc.).  If they all write to a single shared path
# in 'w' mode they overwrite each other.  Unique filenames ensure every process
# contributes its own CSV to the artifact, and archive.py picks all of them up.
_pid = os.getpid()
_ts  = int(time.time() * 1_000_000_000)
log_file = f"{log_dir}/{_ts}_{_pid}.{step_id}.setprofile.csv"

# Open log file (always a fresh file for this process)
profile_log = open(log_file, 'w')
profile_log.write("timestamp_ns,event,function,filename,line\n")
profile_log.flush()

call_count = 0
# Limit applies only to workspace calls (not filtered-out library calls),
# so repo-level data is never truncated early.
max_calls = int(os.environ.get('CINTENT_MAX_CALLS', '5000000'))

def profile_handler(frame, event, arg):
    """
    Profile handler called on every function call/return/exception.

    Events:
    - 'call': function is called
    - 'return': function is returning
    - 'c_call': C function is about to be called
    - 'c_return': C function has returned
    - 'c_exception': C function has raised an exception
    """
    global call_count

    if event not in ('call', 'return'):
        return

    filename = frame.f_code.co_filename

    # Skip the profiler script itself
    if 'setprofile_profiler' in filename:
        return

    # If we know the workspace, only record calls from repo files.
    # This avoids spending the limit on pytest / stdlib initialisation.
    if _workspace and not filename.startswith(_workspace):
        return

    # Limit total logged calls to prevent giant log files
    if call_count >= max_calls:
        return

    call_count += 1
    timestamp_ns = int(time.time() * 1_000_000_000)
    function = frame.f_code.co_name
    line     = frame.f_lineno

    profile_log.write(f"{timestamp_ns},{event},{function},{filename},{line}\n")

    # Flush periodically
    if call_count % 1000 == 0:
        profile_log.flush()

def cleanup():
    """Cleanup on exit"""
    profile_log.flush()
    profile_log.close()
    print(f"[setprofile] Captured {call_count} function calls to {log_file}", file=sys.stderr)

# Register cleanup
atexit.register(cleanup)

# Install the profiler
sys.setprofile(profile_handler)

print(f"[setprofile] Profiling enabled, logging to {log_file}", file=sys.stderr)
