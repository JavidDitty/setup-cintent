#!/bin/bash

set -u

PROFILER_RAW="${CINTENT_PROFILER:-py-spy}"
RATE="${CINTENT_SAMPLE_RATE:-1000}"
TIMESTAMP=$(date +%s%N)
PID="$1"
CINTENT_SETPROFILE_ACTIVE="${CINTENT_SETPROFILE_ACTIVE:-false}"

normalize_profiler() {
    case "$(echo "$1" | tr '[:upper:]' '[:lower:]')" in
        "py-spy"|"py_spy"|"pyspy")
            echo "py-spy"
            ;;
        "perf")
            echo "perf"
            ;;
        "uprobe"|"ebpf"|"usdt")
            echo "uprobe"
            ;;
        "setprofile"|"set_profile"|"set-profile"|"system.profile"|"system_profile"|"system-profile"|"systemprofile"|"sys.setprofile"|"sys_setprofile")
            echo "setprofile"
            ;;
        "sysmonitor"|"sys.monitoring"|"sys_monitoring"|"sysmon"|"monitoring"|"pep669")
            echo "sysmonitor"
            ;;
        *)
            echo ""
            ;;
    esac
}

start_pyspy_record() {
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
}

PROFILER="$(normalize_profiler "$PROFILER_RAW")"
if [ -z "$PROFILER" ]; then
    echo "Unknown profiler: $PROFILER_RAW" >&2
    exit 1
fi

case "$PROFILER" in
    "py-spy")
        # Original py-spy sampling profiler
        start_pyspy_record
        ;;

    "perf")
        # Linux perf with Python call-graph recording.
        # Runs perf record, then converts the binary perf.data to a
        # speedscope JSON file so the cintent parser can process it.
        PERF_DATA="$CINTENT_LOGS/$TIMESTAMP.$CINTENT_STEP_ID.perf.data"
        SPEEDSCOPE_OUT="$CINTENT_LOGS/$TIMESTAMP.$CINTENT_STEP_ID.speedscope.json"
        ERR_FILE="$CINTENT_LOGS/$TIMESTAMP.$CINTENT_STEP_ID.perf.stderr"

        (
            # Locate the perf binary (package name varies by kernel version)
            PERF_BIN=$(command -v perf 2>/dev/null)
            if [ -z "$PERF_BIN" ]; then
                PERF_BIN=$(ls /usr/lib/linux-tools/*/perf 2>/dev/null | sort -V | tail -1)
            fi
            if [ -z "$PERF_BIN" ]; then
                echo "[cintent/perf] No perf binary found. Install linux-tools-generic." \
                    >> "$ERR_FILE"
                exit 0
            fi

            # Record until the target process exits
            sudo "$PERF_BIN" record \
                -p "$PID" \
                -F "$RATE" \
                -g \
                --call-graph dwarf,65528 \
                -o "$PERF_DATA" \
                2>> "$ERR_FILE"

            # Convert binary perf.data -> speedscope JSON
            if [ -f "$PERF_DATA" ] && [ -s "$PERF_DATA" ]; then
                PERF_SCRIPT_TXT="$CINTENT_LOGS/$TIMESTAMP.$CINTENT_STEP_ID.perfscript.tmp"
                sudo "$PERF_BIN" script -i "$PERF_DATA" \
                    > "$PERF_SCRIPT_TXT" 2>> "$ERR_FILE"
                python3 "$CINTENT_PERF_TO_SPEEDSCOPE" \
                    "$PERF_SCRIPT_TXT" "$SPEEDSCOPE_OUT" \
                    2>> "$ERR_FILE"
                sudo rm -f "$PERF_DATA" "$PERF_SCRIPT_TXT"
            else
                echo "[cintent/perf] perf.data missing or empty after recording." \
                    >> "$ERR_FILE"
            fi
        ) &
        echo $! > "$CINTENT_LOGS/perf_$PID.pid"
        ;;

    "uprobe")
        # Python USDT tracing - 100% call coverage via python:function__entry /
        # python:function__return probes.
        #
        # Requirements: Python built with --with-dtrace (Ubuntu 20.04+ default
        # python3 packages ship with USDT probes compiled in).
        #
        # Probe arguments (CPython DTrace probe ABI):
        #   arg0 = filename (char *)
        #   arg1 = funcname (char *)
        #   arg2 = lineno   (int)
        #
        # Duration is computed per call using a tid+depth keyed start-time map
        # so that recursive calls are tracked correctly.

        PYTHON_BIN=$(readlink -f /proc/$PID/exe)
        LOG_FILE="$CINTENT_LOGS/$TIMESTAMP.$CINTENT_STEP_ID.uprobe.log"
        ERR_FILE="$CINTENT_LOGS/$TIMESTAMP.$CINTENT_STEP_ID.uprobe.stderr"

        # Verify all 3 USDT probe arguments are accessible before starting
        # bpftrace.  Python 3.8/3.9 from the GitHub Actions toolcache have
        # incomplete SDT notes: arg1 (funcname) and arg2 (lineno) are missing,
        # so bpftrace errors with "couldn't get argument 1".  When that is the
        # case, the bash wrapper has already activated setprofile as a fallback,
        # so we can exit cleanly here.
        USDT_ARG_COUNT=0
        if command -v readelf &>/dev/null; then
            USDT_ARG_COUNT=$(readelf -n "$PYTHON_BIN" 2>/dev/null \
                | awk '/Name: function__entry/{found=1} found && /Arguments:/{print; exit}' \
                | grep -o '[^ ]*@[^ ]*' | wc -l | tr -d ' ')
        fi
        if [ "${USDT_ARG_COUNT:-0}" -lt 3 ]; then
            echo "[cintent/uprobe] USDT args ${USDT_ARG_COUNT}/3 in $PYTHON_BIN" \
                >> "$ERR_FILE"
            if [ "$CINTENT_SETPROFILE_ACTIVE" == "true" ]; then
                echo "[cintent/uprobe] setprofile fallback active; skipping uprobe attach for PID $PID" \
                    >> "$ERR_FILE"
                exit 0
            fi
            echo "[cintent/uprobe] setprofile fallback not active; using py-spy fallback for PID $PID" \
                >> "$ERR_FILE"
            start_pyspy_record
            exit 0
        fi

        sudo --preserve-env=BPFTRACE_MAX_STRLEN \
            bpftrace \
            -o "$LOG_FILE" \
            -e "
            BEGIN {
                printf(\"timestamp,pid,event,function,file,line,duration_ns\n\");
            }

            usdt:$PYTHON_BIN:python:function__entry
            {
                @depth[tid]++;
                @start[tid, @depth[tid]] = nsecs;
                printf(\"%llu,%d,enter,%s,%s,%d,0\n\",
                    nsecs, pid,
                    str(arg1),
                    str(arg0),
                    (int64)arg2);
            }

            usdt:$PYTHON_BIN:python:function__return
            {
                \$d = @start[tid, @depth[tid]];
                \$dur = \$d ? (nsecs - \$d) : 0;
                delete(@start[tid, @depth[tid]]);
                if (@depth[tid] > 0) { @depth[tid]--; }
                printf(\"%llu,%d,exit,%s,%s,%d,%llu\n\",
                    nsecs, pid,
                    str(arg1),
                    str(arg0),
                    (int64)arg2,
                    \$dur);
            }

            END { clear(@start); clear(@depth); }
            " \
            -p "$PID" \
            2>> "$ERR_FILE" &
        echo $! > "$CINTENT_LOGS/uprobe_$PID.pid"
        ;;

    "setprofile")
        # sys.setprofile() is enabled via sitecustomize.py + PYTHONPATH.
        # No need to attach to running process - profiling starts automatically.
        # This case is a no-op since profiling is handled at Python startup.
        echo "[setprofile] Profiling enabled via sitecustomize.py for PID $PID" >&2
        ;;

    "sysmonitor")
        # sys.monitoring (PEP 669) is enabled via sitecustomize.py + PYTHONPATH.
        # No need to attach to running process - profiling starts automatically
        # when the Python interpreter loads sitecustomize.py.
        # Falls back to sys.setprofile internally on Python < 3.12.
        echo "[sysmonitor] Profiling enabled via sitecustomize.py for PID $PID" >&2
        ;;

    *)
        echo "Unknown profiler: $PROFILER_RAW" >&2
        exit 1
        ;;
esac
