#!/bin/bash

set -u
if [ "$CINTENT_NONBLOCKING" == "true" ]; then
    "$CINTENT_PYSPY" record \
    --pid "$1" \
    --full-filenames \
    --output "$CINTENT_LOGS/$(date +%s%N).$CINTENT_STEP_ID.speedscope.json" \
    --format speedscope \
    --duration unlimited \
    --rate 100 \
    --subprocesses \
    --function \
    --nonblocking \
    > /dev/null &
else
    "$CINTENT_PYSPY" record \
    --pid "$1" \
    --full-filenames \
    --output "$CINTENT_LOGS/$(date +%s%N).$CINTENT_STEP_ID.speedscope.json" \
    --format speedscope \
    --duration unlimited \
    --rate 100 \
    --subprocesses \
    --function \
    > /dev/null &
fi
