#!/usr/bin/env bash
# cli_v2.sh — Delphix CD engine healthcheck (robust config handling)
# Created: 2025-10-08
# Changes vs cli.sh:
#  - Reuses existing FQDN/port/protocol from dxtools.conf when adding rows
#  - Adds --address/--port/--protocol flags to avoid prompts
#  - Normalizes base alias to avoid 'syssys'
#  - Backs up and auto-restores dxtools.conf after run
#  - Optional --preserve-output to keep existing output folders
set -euo pipefail

scriptVersion="3.1.0"

showhelp() {
  cat <<EOF
Script Version ${scriptVersion}
Script to generate Delphix CD healthcheck data

Usage:
  $(basename "$0") -d <engine|all> -t <win|unix|both> -b <dxtoolkit_path> -o <output_dir>
  [--address <fqdn_or_ip>] [--port <port>] [--protocol <http|https>]
  [--password <admin_password>] [--sys-password <sysadmin_password>] [--preserve-output] [-h]

Required dxtoolkit scripts in -b:
  dx_config, dx_ctl_network_tests, dx_ctl_bundle, dx_get_analytics,
  dx_get_capacity, dx_get_appliance, dx_get_storage_tests, dx_get_config

Notes:
  • Set timeouts to 600 in your dxtools.conf entries for long-running calls.
EOF
}

# ---- parse args (supports long options) --------------------------------------
DE_READ=""; DE_TYPE=""; DXLOC=""; MAINDIR=""
ADDR_OPT=""; PORT_OPT=""; PROTO_OPT=""; ADMIN_PASS_OPT=""; SYS_PASS_OPT=""; PRESERVE_OUTPUT=0

if [[ $# -eq 0 ]]; then showhelp; exit 1; fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d) DE_READ="${2:-}"; shift 2 ;;
    -t) DE_TYPE="${2:-}"; shift 2 ;;
    -b) DXLOC="$(cd "${2:-}" && pwd)"; shift 2 ;;
    -o) MAINDIR="$(mkdir -p "${2:-}" && cd "${2:-}" && pwd)"; shift 2 ;;
    --address)   ADDR_OPT="${2:-}"; shift 2 ;;
    --port)      PORT_OPT="${2:-}"; shift 2 ;;
    --protocol)  PROTO_OPT="${2:-}"; shift 2 ;;
    --password)  ADMIN_PASS_OPT="${2:-}"; shift 2 ;;
    --sys-password) SYS_PASS_OPT="${2:-}"; shift 2 ;;
    --preserve-output) PRESERVE_OUTPUT=1; shift 1 ;;
    -h|--help) showhelp; exit 0 ;;
    *) echo "Invalid option: $1"; showhelp; exit 1 ;;
  esac
done

# ---- basic validation (same as original) -------------------------------------
[[ -z "${DE_READ}" ]]  && { echo "Missing -d"; showhelp; exit 1; }
[[ -z "${DE_TYPE}" ]]  && { echo "Missing -t"; showhelp; exit 1; }
[[ -z "${DXLOC}"  ]]   && { echo "Missing -b"; showhelp; exit 1; }
[[ -z "${MAINDIR}" ]]  && { echo "Missing -o"; showhelp; exit 1; }
[[ -d "${MAINDIR}" && -w "${MAINDIR}" ]] || { echo "Can't write to ${MAINDIR}"; exit 1; }

echo "Script Version ${scriptVersion}"
echo "Dxtoolkit Path: ${DXLOC}"

# ---- check dxtoolkit tools exist and support source/binary layouts -----------
require_tool() {
  local name="$1"
  if [[ -x "${DXLOC}/${name}" ]]; then
    return 0
  fi
  echo "Missing executable ${DXLOC}/${name}"
  exit 1
}

run_tool() {
  local name="$1"
  shift
  if [[ -x "${DXLOC}/${name}" ]]; then
    "${DXLOC}/${name}" "$@"
  else
    echo "Missing executable ${DXLOC}/${name}"
    exit 1
  fi
}

require_tool "dx_config"
require_tool "dx_ctl_network_tests"
require_tool "dx_ctl_bundle"
require_tool "dx_get_analytics"
require_tool "dx_get_capacity"
require_tool "dx_get_appliance"
require_tool "dx_get_storage_tests"
require_tool "dx_get_config"

# ---- prepare output dirs -----------------------------------------------------
DATE="$(date '+%Y-%m-%d')"
PERFDATA="${MAINDIR}/analytics"
MISCDIR="${MAINDIR}/misc"
if [[ ${PRESERVE_OUTPUT} -eq 0 ]]; then
  rm -rf "${PERFDATA}" "${MISCDIR}" 2>/dev/null || true
fi
mkdir -p "${PERFDATA}" "${MISCDIR}"

# ---- derive base alias and sys alias (avoid 'syssys') ------------------------
BASE="${DE_READ%sys}"             # strip trailing 'sys' if user passed it
SYS_ALIAS="${BASE}sys"            # normalized sys alias used by sysadmin calls

# ---- read/prepare config safely ---------------------------------------------
cd "${DXLOC}"
DCC="${DXLOC}/dxtools.conf"
CSV="${DXLOC}/.dxconf.csv"
BACKUP=""
cleanup() {
  # restore user's config if we replaced it
  if [[ -n "${BACKUP}" && -f "${BACKUP}" ]]; then
    mv -f "${BACKUP}" "${DCC}"
  fi
  rm -f "${CSV}" 2>/dev/null || true
}
trap cleanup EXIT

# Export existing config to CSV if present (we'll merge rows into CSV)
if [[ -f "${DCC}" ]]; then
  run_tool dx_config -convert tocsv -configfile "${DCC}" -csvfile "${CSV}" >/dev/null || {
    echo "dx_config tocsv failed"; exit 1;
  }
else
  : > "${CSV}"
fi

# helper: read first matching row by alias into variables
read_row() {
  local alias="$1"
  local line
  line="$(grep -m1 "^${alias}," "${CSV}" || true)"
  if [[ -n "${line}" ]]; then
    IFS=',' read -r _ IP PORT USER PASS ENC PROTO <<< "${line}"
    echo "${IP},${PORT},${USER},${PASS},${ENC},${PROTO}"
  fi
}

# get existing admin row (if any)
ADMIN_ROW="$(read_row "${BASE}")" || true
ADMIN_IP=""; ADMIN_PORT=""; ADMIN_USER=""; ADMIN_PASS=""; ADMIN_ENC=""; ADMIN_PROTO=""
if [[ -n "${ADMIN_ROW}" ]]; then
  IFS=',' read -r ADMIN_IP ADMIN_PORT ADMIN_USER ADMIN_PASS ADMIN_ENC ADMIN_PROTO <<< "${ADMIN_ROW}"
fi

# compute target values to use when we must add rows
USE_IP="${ADDR_OPT:-${ADMIN_IP:-${BASE}}}"
USE_PORT="${PORT_OPT:-${ADMIN_PORT:-80}}"
USE_PROTO="${PROTO_OPT:-${ADMIN_PROTO:-http}}"
USE_ENC="${ADMIN_ENC:-false}"

# ensure admin row exists
if ! grep -q "^${BASE}," "${CSV}" ; then
  ADMIN_PASS="${ADMIN_PASS_OPT:-${ADMIN_PASS}}"
  if [[ -z "${ADMIN_PASS}" && "${DE_READ}" != "all" ]]; then
    # Prompt when creating a new engine row and no password exists yet.
    read -r -s -p "Admin password for ${BASE}: " ADMIN_PASS; echo
  fi
  if [[ -z "${ADMIN_PASS}" && "${DE_READ}" != "all" ]]; then
    echo "Missing admin password for ${BASE}."
    exit 1
  fi
  echo "${BASE},${USE_IP},${USE_PORT},admin,${ADMIN_PASS:-},${USE_ENC},${USE_PROTO}" >> "${CSV}"
fi

# ensure sys row exists (reuse address/port/proto)
if ! grep -q "^${SYS_ALIAS}," "${CSV}" ; then
  SYSPASS="${SYS_PASS_OPT}"
  if [[ "${DE_READ}" != "all" ]]; then
    if [[ -z "${SYSPASS}" ]]; then
      read -r -s -p "Sysadmin password for ${SYS_ALIAS}: " SYSPASS; echo
    fi
  fi
  if [[ -z "${SYSPASS}" && "${DE_READ}" != "all" ]]; then
    echo "Missing sysadmin password for ${SYS_ALIAS}."
    exit 1
  fi
  echo "${SYS_ALIAS},${USE_IP},${USE_PORT},sysadmin,${SYSPASS},${USE_ENC},${USE_PROTO}" >> "${CSV}"
fi

# If we are going to change dxtools.conf (add/merge), back it up and write new
if [[ -f "${DCC}" ]]; then
  BACKUP="${DCC}.orig.${DATE}.$$.bak"
  cp -p "${DCC}" "${BACKUP}"
fi
# Write merged CSV back to JSON config for dxtoolkit to use during this run
run_tool dx_config -convert todxconf -configfile "${DCC}" -csvfile "${CSV}" >/dev/null

# ---- build -d flags used by dx_* (same as original, but normalized) ----------
if [[ "${DE_READ}" == "all" ]]; then
  DE="-all"; DESYS="-all"
else
  DE="-d ${BASE}"; DESYS="-d ${SYS_ALIAS}"
fi

# ---- add dxtoolkit to PATH for convenience ----------------------------------
OLDPATH="${PATH}"; export PATH="${DXLOC}:${PATH}"
OLD_DXTOOLKIT_CONF="${DXTOOLKIT_CONF:-}"
export DXTOOLKIT_CONF="${DCC}"

# ---- run tests (unchanged logic, but clearer logging) ------------------------
echo "Run a network latency test on all environments"
if ! run_tool dx_ctl_network_tests ${DE} -c "${DCC}" -type latency -remoteaddr all; then
  echo "Warning: network latency test did not complete successfully; continuing."
fi

echo "Run a network throughput test on all environments"
if ! run_tool dx_ctl_network_tests ${DE} -c "${DCC}" -type throughput -remoteaddr all; then
  echo "Warning: network throughput test did not complete successfully; continuing."
fi

echo "Gathering network latency results -> ${MISCDIR}/${BASE}_NL.csv"
if ! run_tool dx_get_network_tests ${DE} -configfile "${DCC}" -last -type latency -remoteaddr all -format csv > "${MISCDIR}/${BASE}_NL.csv"; then
  echo "Warning: unable to fetch network latency test results; skipping ${MISCDIR}/${BASE}_NL.csv."
fi

echo "Gathering network throughput results -> ${MISCDIR}/${BASE}_NT.csv"
if ! run_tool dx_get_network_tests ${DE} -configfile "${DCC}" -last -type throughput -remoteaddr all -format csv > "${MISCDIR}/${BASE}_NT.csv"; then
  echo "Warning: unable to fetch network throughput test results; skipping ${MISCDIR}/${BASE}_NT.csv."
fi

echo "Gathering analytics (${DE_TYPE})"
case "${DE_TYPE}" in
  win)  ARG_TYPES="cpu,disk,iscsi,network" ;;
  unix) ARG_TYPES="cpu,disk,nfs,network" ;;
  both) ARG_TYPES="cpu,disk,iscsi,nfs,network" ;;
  *)    echo "Invalid -t (use win|unix|both)"; exit 1 ;;
esac
if ! run_tool dx_get_analytics ${DE} -configfile "${DCC}" -i 60 -outdir "${PERFDATA}" -type "${ARG_TYPES}"; then
  echo "Warning: analytics completed with partial errors; continuing with remaining collection tasks."
fi

echo "Gathering capacity -> ${MISCDIR}/${BASE}_capacity.csv"
run_tool dx_get_capacity ${DE} -configfile "${DCC}" -unvirt -format csv > "${MISCDIR}/${BASE}_capacity.csv"

echo "Gathering appliance -> ${MISCDIR}/${BASE}_appliance.csv"
run_tool dx_get_appliance ${DE} -configfile "${DCC}" -format csv > "${MISCDIR}/${BASE}_appliance.csv"

echo "Gathering IORC (sysadmin) -> ${MISCDIR}/"
if ! run_tool dx_get_storage_tests ${DESYS} -configfile "${DCC}" -testid last -iorc "${MISCDIR}"; then
  echo "Warning: no completed storage test found for ${SYS_ALIAS}; skipping IORC export."
fi

echo "Gathering system configuration (sysadmin) -> ${MISCDIR}/${BASE}_config.csv"
run_tool dx_get_config ${DESYS} -configfile "${DCC}" -format csv | sed "s/${SYS_ALIAS}/${BASE}/" > "${MISCDIR}/${BASE}_config.csv"

# ---- restore PATH and config; trap handles final config restore --------------
export PATH="${OLDPATH}"
if [[ -n "${OLD_DXTOOLKIT_CONF}" ]]; then
  export DXTOOLKIT_CONF="${OLD_DXTOOLKIT_CONF}"
else
  unset DXTOOLKIT_CONF
fi

echo "Done. Outputs:"
ls -l "${PERFDATA}"/* 2>/dev/null || true
ls -l "${MISCDIR}"/*  2>/dev/null || true

