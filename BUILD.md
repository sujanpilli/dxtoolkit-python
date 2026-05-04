# Build Guide

## Prerequisites
- Python 3.10+ on the target OS
- `pip` available
- For Windows `.exe` builds: run natively in PowerShell/cmd (not WSL) so PyInstaller emits PE binaries

## Install Dependencies
```bash
pip install -r requirements.txt
```

## Build Standalone Binaries (PyInstaller)
Run on each platform you need binaries for; artifacts land in `dist/`.

Current converted Python entrypoints in `bin/`:
- `dx_ctl_analytics.py`
- `dx_ctl_bundle.py`
- `dx_ctl_network_tests.py`
- `dx_get_analytics.py`
- `dx_get_appliance.py`
- `dx_get_capacity.py`
- `dx_get_config.py`
- `dx_get_dsourcesize.py`
- `dx_get_hierarchy.py`
- `dx_get_jobs.py`
- `dx_get_network_tests.py`
- `dx_get_storage_tests.py`

### macOS/Linux
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
```

### Windows (PowerShell)
```powershell
pip install -r requirements.txt
```
Run PyInstaller directly for the Python entrypoints you need:
```powershell
New-Item -ItemType Directory -Force dist/windows, build/pyinstaller/windows | Out-Null
Get-ChildItem bin\*.py | ForEach-Object {
	py -m PyInstaller --onefile `
		--distpath dist/windows `
		--workpath build/pyinstaller/windows `
		--specpath build/pyinstaller/windows `
		$_.FullName
}
```

## Environment Overrides
- `PYTHON_BIN` (default: `python3`)
- `DIST_DIR` (default base: `dist`; platform output is `dist/macos`, `dist/linux`, or `dist/windows`)
- `WORK_DIR` (default base: `build/pyinstaller`; platform work/spec is under `build/pyinstaller/<platform>`)

## Outputs
- Binaries are written to `dist/macos`, `dist/linux`, or `dist/windows` with one executable per Python entrypoint (`dx_*` and `dx_ctl_*`).

## Legacy Installer Matrix (Release Assets)
If you are producing the classic dxtoolkit installer bundles (runner + install script), the release matrix is:
- amazon2023 installer: dxtoolkit2-<version>-amazon2023-installer.tar.gz
- redhat6 installer: dxtoolkit2-<version>-redhat6-installer.tar.gz
- redhat7 installer: dxtoolkit2-<version>-redhat7-installer.tar.gz
- redhat8 installer: dxtoolkit2-<version>-redhat8-installer.tar.gz
- ubuntu1804 installer: dxtoolkit2-<version>-ubuntu1804-installer.tar.gz
- ubuntu2204 installer: dxtoolkit2-<version>-ubuntu2204-installer.tar.gz
- windows installer: dxtoolkit2-<version>-win64-installer.zip
- osx installer (Intel): dxtoolkit2-<version>-osx.tar.gz
- osx installer (Apple Silicon): dxtoolkit2-<version>-osx-m1.tar.gz

The CI workflow that builds this full set is:
- .github/workflows/build.yml

## Release Checklist
1. Ensure your branch is clean and pushed.
2. Create and push a release tag (example shown for version 2.4.24.2):

```bash
git tag v2.4.24.2
git push origin v2.4.24.2
```

3. Open GitHub Actions and confirm workflow run starts:
- `.github/workflows/build.yml`

4. Verify all platform jobs complete successfully:
- `centos6`
- `centos7`
- `oel8`
- `ubuntu`
- `ubuntu22`
- `amazon2023`
- `Windows`
- `osx`
- `osx-m1`

5. In the release job, verify all expected assets are present:
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
