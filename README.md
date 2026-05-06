# dxtoolkit

> [!CAUTION]
>
> ## Deprecated
>
> This project is now in long-term stasis. If you are using the dxtoolkit today, we recommend that you adopt Data Control Tower (DCT) and migrate your automation to the [DCT Toolkit](https://help.delphix.com/dct/current/content/dct_toolkit.htm). The dxtoolkit was a key input into the introduction of the fully Delphix supported DCT Toolkit.

## What is it

Dxtoolkit is a set of scripts, which are delivered by Delphix professional services team.
Dxtoolkit scripts look and feel like UNIX executables, following the typical conventions of using flags for arguments.  Dxtoolkit is written in Perl, but no knowledge of Perl is required unless you want to extend it.  In fact, no programming experience whatsoever is required to use the dxtoolkit.
### Python Executables (Lightweight Ports)

Recent additions provide Python-based executables for common analytics and network reports:
- `dx_get_network_tests`: export latency/throughput test results to CSV/JSON.
- `dx_get_analytics`: export analytics raw + aggregated CSV/JSON for `cpu, disk, nfs, network`.

Example commands (using compiled binaries from `dist/<platform>/`):

```bash
dx_get_network_tests -d <engine> -type latency -remoteaddr all -format csv
dx_get_network_tests -d <engine> -type throughput -remoteaddr all -last -format csv

dx_get_analytics -d <engine> -type standard -i 60 -outdir /tmp -format csv
```

## Healthcheck CLI scripts

Two equivalent scripts (`cli_v2.sh` for Linux/macOS, `cli_v2.ps1` for Windows) automate a full Delphix engine healthcheck — running network and storage tests, collecting analytics, and exporting capacity, appliance, and configuration data.

### cli_v2.sh (Bash — Linux / macOS)

```
Usage:
  ./cli_v2.sh -d <engine|all> -t <win|unix|both> -b <dxtoolkit_path> -o <output_dir>
              [--address <fqdn_or_ip>] [--port <port>] [--protocol <http|https>]
              [--password <admin_password>] [--sys-password <sysadmin_password>]
              [--preserve-output] [-h|--help]
```

| Flag | Required | Description |
|------|----------|-------------|
| `-d <engine\|all>` | Yes | Engine alias from `dxtools.conf`, or `all` to run against every engine in the config. |
| `-t <win\|unix\|both>` | Yes | Target environment OS type. Determines which analytics types are collected (`iscsi` for Windows, `nfs` for Unix, both if `both`). |
| `-b <dxtoolkit_path>` | Yes | Path to the directory containing the dxtoolkit binaries (or `.py` source files). |
| `-o <output_dir>` | Yes | Directory where output files are written. Created if it does not exist. |
| `--address <fqdn_or_ip>` | No | Override the engine address when adding a new config row. Defaults to the alias name or existing config entry. |
| `--port <port>` | No | Override the port. Defaults to `80` or the existing config value. |
| `--protocol <http\|https>` | No | Override the protocol. Defaults to `http` or the existing config value. |
| `--password <admin_password>` | No | Admin password. Prompted interactively if not supplied and the engine is not already in `dxtools.conf`. |
| `--sys-password <sysadmin_password>` | No | Sysadmin password. Prompted interactively if not supplied and no existing sys row is found. |
| `--preserve-output` | No | Keep any existing `analytics/` and `misc/` folders inside the output directory instead of clearing them. |
| `-h`, `--help` | No | Display help and exit. |

**Output files** (written under `<output_dir>/`):

| File | Content |
|------|---------|
| `misc/<engine>_NL.csv` | Network latency test results |
| `misc/<engine>_NT.csv` | Network throughput test results |
| `misc/<engine>_capacity.csv` | Capacity report |
| `misc/<engine>_appliance.csv` | Appliance/version info |
| `misc/<engine>_config.csv` | System configuration (sysadmin) |
| `misc/` (IORC files) | Storage test IORC data |
| `analytics/` | Analytics CSVs (raw + aggregated) per metric type |

**Required dxtoolkit binaries in `-b` path:**
`dx_config`, `dx_ctl_network_tests`, `dx_ctl_bundle`, `dx_get_analytics`, `dx_get_capacity`, `dx_get_appliance`, `dx_get_storage_tests`, `dx_get_config`, `dx_get_network_tests`

**Examples:**

```bash
# Single engine, Unix environments, with binaries in ./bin
./cli_v2.sh -d myengine -t unix -b ./bin -o ./output

# New engine not yet in dxtools.conf, pass credentials inline
./cli_v2.sh -d myengine -t both -b ./bin -o ./output \
  --address engine.example.com --protocol https \
  --password adminSecret --sys-password sysSecret

# All engines in dxtools.conf, preserve previous output
./cli_v2.sh -d all -t unix -b ./bin -o ./output --preserve-output
```

> **Note:** Set `timeout` to `600` in `dxtools.conf` entries to prevent timeouts on long-running analytics and storage calls. The script backs up and restores `dxtools.conf` automatically on exit.

---

### cli_v2.ps1 (PowerShell — Windows)

```
Usage:
  ./cli_v2.ps1 -d <engine|all> -t <win|unix|both> -b <dxtoolkit_path> -o <output_dir>
               [--address <fqdn_or_ip>] [--port <port>] [--protocol <http|https>]
               [--password <admin_password>] [--sys-password <sysadmin_password>]
               [--preserve-output] [-h|--help]
```

The PowerShell script accepts identical flags to `cli_v2.sh` and produces the same output structure. The key difference is that it expects **Windows `.exe` binaries** in the `-b` path (e.g. `dx_get_analytics.exe`).

| Flag | Required | Description |
|------|----------|-------------|
| `-d <engine\|all>` | Yes | Engine alias from `dxtools.conf`, or `all` for all engines. |
| `-t <win\|unix\|both>` | Yes | Target OS type for analytics collection. |
| `-b <dxtoolkit_path>` | Yes | Path to the directory containing the dxtoolkit `.exe` binaries. |
| `-o <output_dir>` | Yes | Output directory. Created if it does not exist. |
| `--address <fqdn_or_ip>` | No | Override engine address when adding a new config row. |
| `--port <port>` | No | Override port (default `80`). |
| `--protocol <http\|https>` | No | Override protocol (default `http`). |
| `--password <admin_password>` | No | Admin password (prompted if omitted and engine not in config). |
| `--sys-password <sysadmin_password>` | No | Sysadmin password (prompted if omitted). |
| `--preserve-output` | No | Do not clear existing `analytics/` and `misc/` folders. |
| `-h`, `--help` | No | Display help and exit. |

**Required dxtoolkit `.exe` binaries in `-b` path:**
`dx_config.exe`, `dx_ctl_network_tests.exe`, `dx_ctl_bundle.exe`, `dx_get_analytics.exe`, `dx_get_capacity.exe`, `dx_get_appliance.exe`, `dx_get_storage_tests.exe`, `dx_get_config.exe`, `dx_get_network_tests.exe`

**Examples:**

```powershell
# Single engine, Windows environments
./cli_v2.ps1 -d myengine -t win -b .\dist\windows -o .\output

# New engine, pass all credentials inline
./cli_v2.ps1 -d myengine -t both -b .\dist\windows -o .\output `
  --address engine.example.com --protocol https `
  --password adminSecret --sys-password sysSecret

# All engines, preserve existing output
./cli_v2.ps1 -d all -t unix -b .\dist\windows -o .\output --preserve-output
```

> **Note:** Run PowerShell as a user with write access to both the output directory and the dxtoolkit directory (needed to back up `dxtools.conf`). Long-running tool calls stream progress to the console every 5 seconds.

---

## Building standalone binaries (PyInstaller)

Run on each target platform to produce native binaries (macOS/Linux/Windows). Binaries land in `dist/`.
Note: For Windows you must build on Windows (PowerShell/cmd) with Python+PyInstaller installed; WSL builds Linux ELF, not .exe.

```bash
pip install -r requirements.txt
```

Build each Python source file into a standalone binary with PyInstaller. Example:

```bash
platform="$(uname -s | tr '[:upper:]' '[:lower:]')"
if [[ "$platform" == darwin* ]]; then
  platform="macos"
else
  platform="linux"
fi

mkdir -p "dist/$platform" "build/pyinstaller/$platform"
for script in bin/*.py; do
  python3 -m PyInstaller --onefile \
    --distpath "dist/$platform" \
    --workpath "build/pyinstaller/$platform" \
    --specpath "build/pyinstaller/$platform" \
    "$script"
done
# Binaries land in dist/<platform>/ with no .py extension
```

Compiled binaries produced in `dist/<platform>/`:
- `dx_ctl_analytics`
- `dx_ctl_bundle`
- `dx_ctl_network_tests`
- `dx_get_analytics`
- `dx_get_appliance`
- `dx_get_capacity`
- `dx_get_config`
- `dx_get_dsourcesize`
- `dx_get_hierarchy`
- `dx_get_jobs`
- `dx_get_network_tests`
- `dx_get_storage_tests`

> **Windows note:** binaries carry a `.exe` suffix (e.g. `dx_get_analytics.exe`).

Windows PowerShell equivalent:

```powershell
New-Item -ItemType Directory -Force dist/windows, build/pyinstaller/windows | Out-Null
Get-ChildItem bin\*.py | ForEach-Object {
  py -m PyInstaller --onefile `
    --distpath dist/windows `
    --workpath build/pyinstaller/windows `
    --specpath build/pyinstaller/windows `
    $_.FullName
}
# Binaries land in dist\windows\ as .exe files (e.g. dx_get_analytics.exe)
```

Environment overrides:
- `PYTHON_BIN` (default: `python3`)
- `DIST_DIR` (default base: `dist`; platform output is `dist/macos`, `dist/linux`, or `dist/windows`)
- `WORK_DIR` (default base: `build/pyinstaller`; platform work/spec is under `build/pyinstaller/<platform>`)

### Release checklist

1. Ensure your branch is clean and pushed.
2. Create and push a release tag:

```bash
git tag v2.4.24.2
git push origin v2.4.24.2
```

3. Confirm workflow run starts in `.github/workflows/build.yml`.
4. Verify all platform jobs succeed: `centos6`, `centos7`, `oel8`, `ubuntu`, `ubuntu22`, `amazon2023`, `Windows`, `osx`, `osx-m1`.
5. Verify release assets:
  - `dxtoolkit2-v<version>-redhat6-installer.tar.gz`
  - `dxtoolkit2-v<version>-redhat7-installer.tar.gz`
  - `dxtoolkit2-v<version>-redhat8-installer.tar.gz`
  - `dxtoolkit2-v<version>-ubuntu1804-installer.tar.gz`
  - `dxtoolkit2-v<version>-ubuntu2204-installer.tar.gz`
  - `dxtoolkit2-v<version>-amazon2023-installer.tar.gz`
  - `dxtoolkit2-v<version>-win64-installer.zip`
  - `dxtoolkit2-v<version>-osx.tar.gz`
  - `dxtoolkit2-v<version>-osx-m1.tar.gz`
6. Publish the draft release after spot-checking one Linux archive, one macOS archive, and the Windows zip.

The `bin/cli_v2.sh` flow uses these scripts to generate:
- Network latency `*_NL.csv` and throughput `*_NT.csv` into `misc/`.
- Analytics raw and aggregated CSVs into `analytics/`.

### Local runs without an Engine

For smoke testing without a Delphix Engine, a mock is provided:
- `lib/py/mock_engine.py` implements a `MockEngine` with minimal responses.
Tests demonstrate monkeypatching the `engine` module to use it.
See `test/test_json_outputs.py` for examples.


## What's new

Please check a [change log](https://github.com/delphix/dxtoolkit/blob/master/CHANGELOG.md) for list of changes.

## How to get started
### Compiled version

Download a compiled version of DxToolkit for required platform from a [releases  page](https://github.com/delphix/dxtoolkit/releases).
Create a configuration file *dxtools.conf* based on dxtools.conf.example or a Wiki page.

Check a [documentation](https://github.com/delphix/dxtoolkit/wiki) for more details


### Docker image

Run dxtoolkit using a docker image:
1. Create configuration file *dxtools.conf* based on dxtools.conf.example or a Wiki page.
2. Run a docker image with the following parameters:
  * path redirection: `-v /path/to/your/configfile:/config`
  * image name: `pioro/dxtoolkit:develop`
  * `dxtoolkit_command dxtoolkit_command_params`


   ex: `docker run -v /configdir:/config pioro/dxtoolkit:latest dx_get_appliance -d myengine`


### Source version

Perl version 5.16 or higher

**Required packages**
- JSON
- Date::Manip
- DateTime::Event::Cron::Quartz
- DateTime::Format::DateParse
- Crypt::CBC
- Crypt::Blowfish
- Text::CSV
- Try::Tiny
- LWP::UserAgent
- Net::SSLeay
- IO::Socket::SSL
- LWP::Protocol::https
- Term::ReadKey
- Log::Syslog::Fast


### Known issues

There is no script dx_syslog on Windows and AIX due to lack of support of Log::Syslog::Fast Perl module


### Support matrix

New releases of dxtoolkit are tested with Delphix Engines, which are in primary or extended support.
Ex. 2.4.14 release was tested with version 5.3.9 and 6.0.X engines.

Dxtoolkit is designed to support many versions of Delphix Engines, although if a new version is released after dxtoolkit release
it may stop working due to API changes. To mitigate this issue until next dxtoolkit version will be release, please add
-dever parameter to your commands with the following values:

|parameter|Delphix Engine version|API version|
| :---    |     :---:            | :---      |
| -dever 6.0.11| Delphix Engine 6.0.11 | API 1.11.11|
| -dever 6.0| Delphix Engine 6.0 | API 1.11.00|
| -dever 5.3| Delphix Engine 5.3 | API 1.10.00|
| -dever 5.2| Delphix Engine 5.2 | API 1.9.00|



## <a id="contribute"></a>Contribute

1.  Fork the project.
2.  Make your bug fix or new feature.
3.  Add tests for your code.
4.  Send a pull request.

Contributions must be signed as `User Name <user@email.com>`. Make sure to [set up Git with user name and email address](https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup). Bug fixes should branch from the current stable branch. New features should be based on the `master` branch.

#### <a id="code-of-conduct"></a>Code of Conduct

This project operates under the [Delphix Code of Conduct](https://delphix.github.io/code-of-conduct.html). By participating in this project you agree to abide by its terms.

#### <a id="contributor-agreement"></a>Contributor Agreement

All contributors are required to sign the Delphix Contributor agreement prior to contributing code to an open source repository. This process is handled automatically by [cla-assistant](https://cla-assistant.io/). Simply open a pull request and a bot will automatically check to see if you have signed the latest agreement. If not, you will be prompted to do so as part of the pull request process.


## <a id="reporting_issues"></a>Reporting Issues

Issues should be reported in the GitHub repo's issue tab. Include a link to it.

## <a id="statement-of-support"></a>Statement of Support

This software is provided as-is, without warranty of any kind or commercial support through Delphix. See the associated license for additional details. Questions, issues, feature requests, and contributions should be directed to the community as outlined in the [Delphix Community Guidelines](https://delphix.github.io/community-guidelines.html).


## <a id="license"></a>License
```
 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
```
Copyright (c) 2014, 2016 by Delphix. All rights reserved.
