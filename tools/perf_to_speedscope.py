#!/usr/bin/env python3
"""
Convert `perf script` text output to speedscope JSON format.

Usage:
    python3 perf_to_speedscope.py <perf_script_output.txt> <out.speedscope.json>

The `perf script` text output is produced by:
    perf script -i file.perf.data

Each sample block looks like:
    python3 1234 [001] 123456.789012:    1000000 cpu-clock:
            7f1234abcd _PyEval_EvalFrameDefault+0x3ab (/usr/bin/python3.10)
            7f1234ef01 PyObject_Call+0x12 (/usr/bin/python3.10)
            ...

    [blank line separates samples]

The resulting speedscope JSON uses the 'sampled' profile type, which is the
same format py-spy produces, so the existing cintent parser handles it without
any changes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Sample header:  comm  pid  [cpu]  time:  count  event_name:
_HEADER_RE = re.compile(
    r'^(\S+)\s+(\d+)\s+(?:\[[\d ]+\]\s+)?([\d.]+):\s+(\d+)\s+\S'
)

# Stack frame:  leading-whitespace  addr  sym+offset  (binary_or_dso)
_FRAME_RE = re.compile(
    r'^\s+[0-9a-f]+\s+(.*?)(?:\+0x[0-9a-f]+)?\s+\(([^)]*)\)\s*$'
)


def _parse_blocks(text: str) -> list[dict]:
    """Split perf script text into per-sample dictionaries."""
    samples: list[dict] = []
    current: dict | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        # Blank line → flush current sample
        if not line.strip():
            if current and current.get('stack'):
                samples.append(current)
            current = None
            continue

        # Try to match a sample header
        m = _HEADER_RE.match(line)
        if m:
            if current and current.get('stack'):
                samples.append(current)
            current = {
                'comm': m.group(1),
                'pid': int(m.group(2)),
                'time_s': float(m.group(3)),
                'weight': int(m.group(4)),
                'stack': [],
            }
            continue

        # Try to match a stack frame
        if current is not None:
            m = _FRAME_RE.match(line)
            if m:
                sym_raw = m.group(1).strip()
                # Strip inlined marker prefix (some perf versions add it)
                sym = sym_raw.lstrip('(').split()[0]
                dso = m.group(2).strip()
                if sym and sym not in ('[unknown]', '0'):
                    current['stack'].append({'name': sym, 'file': dso})

    # Flush final sample
    if current and current.get('stack'):
        samples.append(current)

    return samples


# ---------------------------------------------------------------------------
# Speedscope JSON construction
# ---------------------------------------------------------------------------

def _build_speedscope(samples: list[dict]) -> dict[str, Any]:
    """Convert parsed perf samples into a speedscope JSON dict."""
    # Deduplicate frames: (name, file) → index
    frame_index: dict[tuple[str, str], int] = {}
    frames: list[dict] = []

    def _get_frame_idx(name: str, file: str) -> int:
        key = (name, file)
        if key not in frame_index:
            frame_index[key] = len(frames)
            frames.append({'name': name, 'file': file})
        return frame_index[key]

    speedscope_samples: list[list[int]] = []
    speedscope_weights: list[int] = []

    for s in samples:
        # Reverse the stack so that the outermost caller is first
        # (speedscope convention: index 0 = bottom of call stack)
        frame_ids = [_get_frame_idx(f['name'], f['file']) for f in reversed(s['stack'])]
        if frame_ids:
            speedscope_samples.append(frame_ids)
            speedscope_weights.append(s['weight'])

    if not speedscope_samples:
        return {}

    start_ns = int(samples[0]['time_s'] * 1e9)
    end_ns = int(samples[-1]['time_s'] * 1e9)
    # Ensure end > start even for very short recordings
    if end_ns <= start_ns:
        end_ns = start_ns + sum(speedscope_weights)

    return {
        '$schema': 'https://www.speedscope.app/file-format-schema.json',
        'shared': {'frames': frames},
        'profiles': [
            {
                'type': 'sampled',
                'name': 'perf',
                'unit': 'nanoseconds',
                'startValue': start_ns,
                'endValue': end_ns,
                'samples': speedscope_samples,
                'weights': speedscope_weights,
            }
        ],
        'name': 'perf profile',
        'activeProfileIndex': 0,
        'exporter': 'cintent/perf_to_speedscope',
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Convert perf script output to speedscope JSON'
    )
    parser.add_argument('input', help='perf script text output file (or - for stdin)')
    parser.add_argument('output', help='speedscope JSON output path')
    args = parser.parse_args()

    if args.input == '-':
        text = sys.stdin.read()
    else:
        with open(args.input, 'r', errors='replace') as f:
            text = f.read()

    samples = _parse_blocks(text)
    if not samples:
        print('[cintent/perf_to_speedscope] No samples found in perf output.',
              file=sys.stderr)
        sys.exit(1)

    result = _build_speedscope(samples)
    if not result:
        print('[cintent/perf_to_speedscope] Failed to build speedscope profile.',
              file=sys.stderr)
        sys.exit(1)

    with open(args.output, 'w') as f:
        json.dump(result, f)

    n_samples = len(result['profiles'][0]['samples'])
    n_frames = len(result['shared']['frames'])
    print(
        f'[cintent/perf_to_speedscope] Converted {n_samples} samples '
        f'({n_frames} unique frames) → {args.output}',
        file=sys.stderr,
    )


if __name__ == '__main__':
    main()
