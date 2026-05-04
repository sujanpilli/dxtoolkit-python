# Python vs Perl Parity Test Report

Date: 2026-04-30
Workspace: dxtoolkit-working
Branch: python_conversion

## Scope
Tested all bin scripts that have both a `.pl` and `.py` implementation:

- dx_ctl_analytics
- dx_ctl_bundle
- dx_ctl_network_tests
- dx_get_analytics
- dx_get_appliance
- dx_get_capacity
- dx_get_config
- dx_get_dsourcesize
- dx_get_hierarchy
- dx_get_jobs
- dx_get_network_tests
- dx_get_storage_tests

## Environment Setup
- Created local venv: `.venv`
- Installed Python dependencies from `requirements.txt`
- Executed Perl scripts from `bin/` to satisfy Perl relative library paths

## Test A: Version Output Parity (All Paired Scripts)
Command pattern: script-specific required args + `-version`

Result summary:
- Output parity: 11/12 scripts matched exactly (`2.4.24.2`)
- Exit code parity: 0/12 matched

Details:
- 11 scripts: Perl output matched Python output; Perl exit code was 255, Python exit code was 0.
- `dx_get_hierarchy`: Perl failed before argument handling due missing Perl module `DateTime::Event::Cron::Quartz`; Python printed version correctly.

## Test B: Validation/Error-Path Behavior (Converted `dx_get_*` scripts)
Compared Perl vs Python output for argument-validation paths (no live engine required):

### dx_get_capacity
- `-all -d engine1`: same semantic message, same exit code (1), not byte-identical due Perl usage text appended
- `-output_unit Z`: same semantic message, same exit code (1), not byte-identical due Perl usage text appended

### dx_get_dsourcesize
- `-all -d engine1`: same semantic message, same exit code (1), not byte-identical due Perl usage text appended
- `-output_unit Z`: mismatch
  - Perl path hit runtime message `Missing output conversion` after banner (exit 255)
  - Python rejects invalid unit early with explicit validation message (exit 1)

### dx_get_jobs
- `-state BADSTATE`: same semantic message, same exit code (1), not byte-identical due Perl usage text appended
- `-all -d engine1`: same semantic message, same exit code (1), not byte-identical due Perl usage text appended

### dx_get_hierarchy
- `-all -d engine1`: not comparable
  - Perl fails at startup due missing Perl dependency `DateTime::Event::Cron::Quartz`
  - Python reaches argument validation and returns the mutual-exclusion message

## Conclusion
- Python conversions are generally aligned with Perl in user-facing messages for tested validation paths.
- Two parity blockers are external to Python logic:
  1. Perl startup dependency issue for `dx_get_hierarchy.pl` (missing Perl module).
  2. Perl `-version` convention returns exit code 255 via `die`, while Python returns exit code 0.
- One behavioral divergence found:
  - `dx_get_dsourcesize -output_unit Z` handling differs (Python now validates earlier and more explicitly).

## Rerun With Explicit Perl Library Path
After installing missing Perl modules locally and running with:

- `PERL5LIB=/Users/sujan.pilli/workspaces/dxtoolkit-working/.perl5/lib/perl5`

the full paired matrix (`12/12`) for `-version` was revalidated.

Rerun result summary:
- Output parity: `12/12` scripts matched exactly (`2.4.24.2`)
- Exit code parity: `0/12` matched

Exit-code mismatch is expected due implementation difference:
- Perl uses `die "$version\n"` for `-version` (exit `255`)
- Python prints version and returns `0`

## Real Engine Test Using dxtools.conf
Used the real engine configuration from `bin/dxtools.conf` and executed read-only `dx_get_*` commands against the default engine.

Environment for live Perl runs:
- `PERL5LIB=/Users/sujan.pilli/workspaces/dxtoolkit-working/.perl5/lib/perl5`

Environment for live Python runs:
- `../.venv/bin/python`

### Live Comparison Summary

#### `dx_get_appliance`
- Perl exit code: `0`
- Python exit code: `0`
- Raw JSON match: `No`
- Semantic match after normalization: `Yes`
- Difference: Perl preserves width-padded numeric strings in JSON; Python emits trimmed numeric strings.

#### `dx_get_capacity`
- Perl exit code: `0`
- Python exit code: `0`
- Raw JSON match: `No`
- Semantic match after normalization: `Yes`
- Difference: formatting only (whitespace padding / ordering).

#### `dx_get_jobs`
- Perl exit code: `0`
- Python exit code: `0`
- Raw JSON match: `Yes`
- Semantic match after normalization: `Yes`

#### `dx_get_dsourcesize`
- Perl exit code: `0`
- Python exit code: `0`
- Raw JSON match: `No`
- Semantic match after normalization: `Yes`
- Notes:
  - Both outputs include the same comment banner before JSON.
  - Raw JSON still differs because Perl preserves width-padded strings and ordering.
  - After normalizing whitespace and sorting results by database name, Perl and Python outputs match.
  - The parity fix required resolving dSource metadata from `source -> sourceconfig -> repository -> environment` and aligning the Python engine session with the engine's reported API version before login.

#### `dx_get_hierarchy`
- Perl exit code: `2`
- Python exit code: `0`
- Result: not comparable
- Perl stderr:
  - `Use of uninitialized value ... at Date/Manip/TZ.pm`
  - `Can't use an undefined value as an ARRAY reference at Date/Manip/Base.pm`
- Python successfully returned JSON data.
- Conclusion: the Perl script crashes at runtime against this engine, so live output parity cannot be established for this command in the current environment.
