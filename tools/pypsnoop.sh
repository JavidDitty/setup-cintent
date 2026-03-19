#!/bin/bash

set -u

PROFILER="${CINTENT_PROFILER:-py-spy}"
RATE="${CINTENT_SAMPLE_RATE:-1000}"
TIMESTAMP=$(date +%s%N)
PID="$1"

case "$PROFILER" in
    "py-spy")
        # Original py-spy sampling profiler
        if [ "$CINTENT_NONBLOCKING" == "true" ]; then
            "$CINTENT_PYSPY" record \
            --pid "$PID" \
            --full-filenames \
            --output "$CINTENT_LOGS/$TIMESTAMP.$CINTENT_STEP_ID.speedscope.json" \
            --format speedscope \
            --duration unlimited \
            --rate "$RATE" \
            --subprocesses \
            --function \
            --nonblocking \
            > /dev/null &
        else
            "$CINTENT_PYSPY" record \
            --pid "$PID" \
            --full-filenames \
            --output "$CINTENT_LOGS/$TIMESTAMP.$CINTENT_STEP_ID.speedscope.json" \
            --format speedscope \
            --duration unlimited \
            --rate "$RATE" \
            --subprocesses \
            --function \
            > /dev/null &
        fi
        ;;

    "perf")
        # Linux perf with Python support
        sudo perf record \
            -p "$PID" \
            -F "$RATE" \
            -g \
            --call-graph dwarf \
            -o "$CINTENT_LOGS/$TIMESTAMP.$CINTENT_STEP_ID.perf.data" \
            &> /dev/null &
        echo $! > "$CINTENT_LOGS/perf_$PID.pid"
        ;;

    "uprobe")
        # eBPF uprobe tracing - captures ALL calls
        sudo bpftrace \
            -o "$CINTENT_LOGS/$TIMESTAMP.$CINTENT_STEP_ID.uprobe.log" \
            "$CINTENT_PYPSNOOP_UPROBE" \
            -p "$PID" \
            &> /dev/null &
        echo $! > "$CINTENT_LOGS/uprobe_$PID.pid"
        ;;

    "setprofile")
        # sys.setprofile() is enabled via PYTHONPROFILE env var
        # No need to attach to running process - profiling starts automatically
        # This case is a no-op since profiling is handled at Python startup
        echo "[setprofile] Profiling enabled via PYTHONPROFILE for PID $PID" >&2
        ;;

    *)
        echo "Unknown profiler: $PROFILER" >&2
        exit 1
        ;;
esac
