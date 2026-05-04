#!/usr/bin/env python3
"""Python port of dx_config.pl.

Convert dxtools.conf to/from CSV and support one-line text input conversion.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'lib', 'py'))

import toolkit_helpers


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Convert dxtools.conf to/from CSV",
        add_help=False,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("-help", "-h", "--help", "-?", dest="help", action="store_true")
    parser.add_argument("-debug", action="store_true")
    parser.add_argument("-convert", dest="convert")
    parser.add_argument("-csvfile", "-f", dest="csvfile")
    parser.add_argument("-append", action="store_true")
    parser.add_argument("-text", dest="conf_param_file")
    parser.add_argument("-configfile", "-c", dest="configfile")
    parser.add_argument("-version", "-v", dest="print_version", action="store_true")
    return parser, parser.parse_args(argv)


def _load_conf_data(configfile):
    with open(configfile, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload.get("data", []) if isinstance(payload, dict) else []


def _backup_config_if_exists(configfile):
    if os.path.exists(configfile):
        stamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        backupfile = f"{configfile}.{stamp}"
        shutil.copy2(configfile, backupfile)
        print(f"Old config file backup file name is {backupfile} ")


def _engine_from_fields(raw_line):
    parts = raw_line.split(",")
    parts += [""] * (9 - len(parts))
    hostname, ip_address, port, username, password, default, protocol, clientid, clientsecret = parts[:9]

    required_ok = all(v is not None for v in [hostname, ip_address, port, default])
    creds_ok = ((username != "" and password != "") or (clientid != "" and clientsecret != ""))
    if not (required_ok and creds_ok):
        print(f"There is a problem with line {raw_line} ")
        print("Not all fields defined. Exiting")
        raise ValueError("invalid fields")

    if username != "" and clientid != "":
        print(f"There is a problem with line {raw_line} ")
        print("username and clientid are mutually exclusive")
        raise ValueError("mutually exclusive fields")

    if username != "":
        return {
            "hostname": hostname,
            "username": username,
            "ip_address": ip_address,
            "password": password,
            "port": port,
            "default": default,
            "protocol": protocol,
        }

    return {
        "hostname": hostname,
        "clientid": clientid,
        "ip_address": ip_address,
        "clientsecret": clientsecret,
        "port": port,
        "default": default,
        "protocol": protocol,
    }


def convert_todxconf(csvfile, configfile):
    engine_list = []
    with open(csvfile, "r", encoding="utf-8") as fd:
        for raw in fd:
            line = raw.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            engine_list.append(_engine_from_fields(line))

    _backup_config_if_exists(configfile)
    payload = {"data": engine_list}
    with open(configfile, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=4)
        fh.write("\n")
    print(f"New config file {configfile} created.")


def _existing_engines_for_append(configfile):
    existing = []
    for item in _load_conf_data(configfile):
        if not isinstance(item, dict):
            continue
        eng = dict(item)
        hostname = eng.get("hostname") or eng.get("name") or eng.get("engine")
        if hostname:
            eng["hostname"] = hostname
            existing.append(eng)
    return existing


def convert_text_todxconf(conf_param_file, configfile, append):
    engine_list = []

    if append and not os.path.exists(configfile):
        print("Config file must exist for append option")
        return 1
    if append:
        engine_list.extend(_existing_engines_for_append(configfile))

    line = conf_param_file.strip()
    if line and not line.startswith("#"):
        try:
            engine_list.append(_engine_from_fields(line))
        except ValueError:
            return 1

    _backup_config_if_exists(configfile)
    payload = {"data": engine_list}
    with open(configfile, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=4)
        fh.write("\n")
    print(f"New config file {configfile} created.")
    return 0


def convert_tocsv(csvfile, configfile):
    data = _load_conf_data(configfile)

    with open(csvfile, "w", encoding="utf-8") as fd:
        fd.write("# engine nick name, engine ip/hostname, port, username, password, default, protocol, clientid, clientsecret \n")
        for engine in data:
            if not isinstance(engine, dict):
                continue
            engine_name = engine.get("hostname") or engine.get("name") or engine.get("engine") or ""
            ip_address = engine.get("ip_address", "")
            port = engine.get("port", "")
            default = engine.get("default", "")
            protocol = engine.get("protocol", "")
            clientid = engine.get("clientid", "")
            clientsecret = engine.get("clientsecret", "")
            username = engine.get("username", "")
            password = engine.get("password", "")

            if clientid:
                line = f"{engine_name},{ip_address},{port},,,{default},{protocol},{clientid},{clientsecret}\n"
            else:
                line = f"{engine_name},{ip_address},{port},{username},{password},{default},{protocol},,\n"
            fd.write(line)

    print(f"New csv file {csvfile} created.")


def main(argv):
    parser, args = parse_args(argv)

    if args.help:
        parser.print_help()
        return 0

    if args.print_version:
        print(toolkit_helpers.version)
        return 0

    if not (args.convert and (args.csvfile or args.conf_param_file) and args.configfile):
        print("Parameter convert is required.")
        parser.print_help(sys.stderr)
        return 1

    if args.convert not in ("tocsv", "todxconf"):
        print("Parameter convert has to possible value tocsv and todxconf")
        parser.print_help(sys.stderr)
        return 1

    try:
        if args.convert == "tocsv":
            convert_tocsv(args.csvfile, args.configfile)
            return 0

        if args.convert == "todxconf" and args.csvfile:
            convert_todxconf(args.csvfile, args.configfile)
            return 0

        if args.convert == "todxconf" and args.conf_param_file:
            return convert_text_todxconf(args.conf_param_file, args.configfile, args.append)
    except FileNotFoundError as exc:
        print(f"Can't open file: {exc.filename}")
        return 1
    except PermissionError as exc:
        print(f"Can't open file: {exc.filename}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
