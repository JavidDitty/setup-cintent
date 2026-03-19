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
        # Detect actual Python binary path from PID
        PYTHON_BIN=$(readlink -f /proc/$PID/exe)

        sudo bpftrace \
            -o "$CINTENT_LOGS/$TIMESTAMP.$CINTENT_STEP_ID.uprobe.log" \
            -e "
            BEGIN { printf(\"timestamp,pid,event,function,file,line,duration_ns\n\"); }
            uprobe:$PYTHON_BIN:PyEval_EvalFrameEx,
            uprobe:$PYTHON_BIN:_PyEval_EvalFrameDefault
            {
                \$frame = (struct frame *)arg0;
                @start[tid] = nsecs;
                @frame[tid] = \$frame;
                printf(\"%llu,%d,enter,%s,%s,%d,0\n\",
                    nsecs, pid,
                    str(\$frame->f_code->co_name),
                    str(\$frame->f_code->co_filename),
                    \$frame->f_lineno);
            }
            uretprobe:$PYTHON_BIN:PyEval_EvalFrameEx,
            uretprobe:$PYTHON_BIN:_PyEval_EvalFrameDefault
            /@start[tid]/
            {
                \$duration = nsecs - @start[tid];
                \$frame = @frame[tid];
                printf(\"%llu,%d,exit,%s,%s,%d,%llu\n\",
                    nsecs, pid,
                    str(\$frame->f_code->co_name),
                    str(\$frame->f_code->co_filename),
                    \$frame->f_lineno,
                    \$duration);
                delete(@start[tid]);
                delete(@frame[tid]);
            }
            END { clear(@start); clear(@frame); }
            " \
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
