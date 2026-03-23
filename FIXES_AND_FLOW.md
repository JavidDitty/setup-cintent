# CIntent Profiler Reliability Fixes and End-to-End Flow

## Problem Summary

Only `py-spy` traces were parsing into non-empty `sandwich.csv` / `graph.csv`.  
`system.profile` and some `uprobe` runs produced empty parse outputs.

## Root Causes Identified

1. Profiler name mismatch:
- Action logic expected `setprofile`, but workflows used aliases like `system.profile`.
- Result: setprofile bootstrap was never activated, so no `.setprofile.csv` trace files were produced.

2. Uprobe attach incompatibility on some Python builds:
- Python 3.8/3.9 GitHub toolcache binaries can expose incomplete USDT probe arguments.
- Result: uprobe attach failed (`couldn't get argument 1`), giving empty `.uprobe.log`.

3. Parser file-type strictness:
- Archive parser assumed exactly `timestamp.step_id.file_type.extension` with exactly 4 tokens.
- Filenames with dotted profiler types (for example `system.profile`) were not parsed.

4. Snooper startup checks used incorrect grep patterns/logic:
- Header checks used `\s` with plain grep and inverted success checks.
- This could cause startup detection issues and noisy failures.

## Files Changed

1. `setup-cintent/action.yml`
- Added profiler normalization:
  - `system.profile`, `system_profile`, `system-profile`, `sys.setprofile` -> `setprofile`
  - `pyspy`, `py_spy` -> `py-spy`
  - Also normalizes case.
- Added fast validation for unsupported profiler values (explicit failure with message).
- Added metadata keys:
  - `profiler_requested`
  - `profiler`
- Added `CINTENT_SETPROFILE_ACTIVE` env flag.
- Fixed execsnoop/opensnoop startup regex checks (`grep -E` + `[[:space:]]+`) and corrected pass/fail logic.
- Refactored setprofile bootstrap into helper `_cintent_enable_setprofile`.
- Improved uprobe fallback pre-check:
  - Checks both `python` and `python3` binaries for USDT argument availability.
  - Activates setprofile fallback when any candidate is incompatible.

2. `setup-cintent/tools/pypsnoop.sh`
- Added profiler normalization (same alias support as action level).
- Added shared helper `start_pyspy_record`.
- In uprobe mode, if USDT args are missing:
  - If `CINTENT_SETPROFILE_ACTIVE=true`, skip uprobe and rely on setprofile output.
  - Otherwise, automatically fall back to `py-spy` for that PID to avoid empty traces.
- Updated setprofile mode comment to reflect `sitecustomize.py + PYTHONPATH` behavior.

3. `cintent/src/cintent/archive.py`
- Added `_normalize_file_type` for parser-side compatibility:
  - `system.profile`/`system_profile`/`system-profile`/`systemprofile` -> `setprofile`
  - `pyspy` -> `speedscope`
- Relaxed filename parsing to support file types containing dots:
  - Requires `>= 4` parts instead of exactly 4.
  - Uses first two parts as `timestamp`, `step_id`, and joins middle parts as `file_type`.
- Extended combined metadata schema with:
  - `profiler_requested`
  - `profiler`

## End-to-End Runtime Logic (Updated)

1. `setup-cintent` initializes environment variables and normalizes profiler name.
2. Wrapper `bash` is injected into PATH.
3. For each traced step:
- Metadata file is created.
- BPF tools (`execsnoop`, `opensnoop`, etc.) start.
- Startup headers are verified correctly.
- Profiler behavior:
  - `py-spy`: attach and write `*.speedscope.json`
  - `perf`: record + convert to `*.speedscope.json`
  - `uprobe`: attempt USDT attach; fallback to setprofile or py-spy if unsupported
  - `setprofile` (or alias `system.profile`): inject `sitecustomize.py`, write `*.setprofile.csv`
4. All logs are uploaded as artifact zip.
5. `cintent` parser loads artifact:
- Reads `*.functions.csv`
- Parses metadata
- Converts speedscope / uprobe / setprofile traces into:
  - `*_sandwich.csv`
  - `*_graph.csv`
  - `*_metadata.csv`

## Recommended Profiler Values in Workflow

Use these canonical values in workflow files:
- `sysmonitor` (default — sys.monitoring PEP 669, 100% coverage, ~2-3% overhead)
- `py-spy`
- `perf`
- `uprobe`
- `setprofile`

Aliases now work, but canonical values are still recommended for readability.

