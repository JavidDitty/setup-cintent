#!/bin/bash

set -u

# Use perf to record Python call stacks
# -F sets frequency (lower = less overhead)
# -g enables call graph recording
# --call-graph dwarf for better Python support

FREQ="${CINTENT_SAMPLE_RATE:-1000}"

perf record \
    -p "$1" \
    -F "$FREQ" \
    -g \
    --call-graph dwarf \
    -o "$CINTENT_LOGS/$(date +%s%N).$CINTENT_STEP_ID.perf.data" \
    &> /dev/null &

# Store the perf PID for cleanup
echo $! > "$CINTENT_LOGS/perf_$1.pid"
