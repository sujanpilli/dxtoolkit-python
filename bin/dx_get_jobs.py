#!/usr/bin/env python3
"""Python port of dx_get_jobs.pl."""
import argparse
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'lib', 'py'))

from engine import Engine
from databases import Databases
from group_obj import GroupObj
from formater import Formater
import toolkit_helpers


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Get Delphix Engine jobs')
    parser.add_argument('-d', '--engine', dest='dx_host')
    parser.add_argument('-st', dest='st')
    parser.add_argument('-et', dest='et')
    parser.add_argument('-state', dest='state')
    parser.add_argument('-jobref', dest='jobref')
    parser.add_argument('-dbname', dest='dbname')
    parser.add_argument('-type', dest='jtype')
    parser.add_argument('-group', dest='group')
    parser.add_argument('-host', dest='host')
    parser.add_argument('-errDetails', action='store_true')
    parser.add_argument('-outdir', dest='outdir')
    parser.add_argument('-dsource', dest='dsource')
    parser.add_argument('-format', dest='fmt')
    parser.add_argument('-all', action='store_true')
    parser.add_argument('-version', action='store_true')
    parser.add_argument('-dever', dest='dever')
    parser.add_argument('-nohead', action='store_true')
    parser.add_argument('-debug', dest='debug', type=int, nargs='?', const=1)
    parser.add_argument('-configfile', '-c', dest='config_file')
    return parser.parse_args(argv)


def _ts_for_api(raw, eng, default_7_days=False):
    if raw is None:
        if default_7_days:
            return eng.getTime(7 * 24 * 60)
        return None
    parsed = toolkit_helpers.parse_timestamp(raw, eng.getTimezone())
    return parsed


def _format_time_with_tz(ts, tz):
    if not ts:
        return ''
    return toolkit_helpers.convert_from_utc(ts, tz, 1)


def _runtime_hms(start_ts, end_ts):
    if not start_ts or not end_ts:
        return '00:00:00'

    def _parse_iso(value):
        txt = str(value)
        if txt.endswith('Z'):
            txt = txt[:-1] + '+00:00'
        try:
            return datetime.fromisoformat(txt)
        except Exception:
            try:
                return datetime.strptime(str(value), '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
            except Exception:
                return datetime.strptime(str(value), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)

    try:
        st = _parse_iso(start_ts)
        et = _parse_iso(end_ts)
        if et < st:
            return '00:00:00'
        secs = int((et - st).total_seconds())
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        return f'{h:02d}:{m:02d}:{s:02d}'
    except Exception:
        return '00:00:00'


def _collect_users(engine_obj):
    op = 'resources/json/delphix/user'
    result, _fmt, rc = engine_obj.getJSONResult(op)
    users = {}
    if rc or result.get('status') != 'OK':
        return users
    for item in result.get('result', []):
        if item.get('namespace'):
            continue
        ref = item.get('reference')
        if ref:
            users[ref] = item.get('name') or item.get('username') or item.get('principal') or 'N/A'
    return users


def _db_display_map(databases, groups):
    mapping = {}
    for dbref in databases.getDBList():
        dbobj = databases.getDB(dbref) or {}
        dbname = databases.getName(dbref) or dbobj.get('name') or dbref
        gname = groups.getName(dbobj.get('group')) or ''
        mapping[dbref] = f'{gname}/{dbname}'

        src = dbobj.get('source') or {}
        src_ref = src.get('reference')
        if src_ref:
            mapping[src_ref] = f'{gname}/{dbname}'

        staging = dbobj.get('staging_source') or {}
        staging_ref = staging.get('reference')
        if staging_ref:
            mapping[staging_ref] = f'Staging - {dbname}'

    return mapping


def _matches_type(job, desired):
    if not desired:
        return True
    action_type = str(job.get('actionType') or '')
    return desired in action_type


def _fetch_jobs_for_target(engine_obj, target_ref, from_ts, to_ts, state, add_events):
    jobs = {}
    page_size = 5000
    offset = 0

    while True:
        op = f'resources/json/delphix/job?pageSize={page_size}&pageOffset={offset}'
        if target_ref:
            op += f'&target={target_ref}'
        if from_ts:
            op += f'&fromDate={from_ts}'
        if to_ts:
            op += f'&toDate={to_ts}'
        if state:
            op += f'&jobState={state.upper()}'
        if add_events:
            op += '&addEvents=true'

        result, _fmt, rc = engine_obj.getJSONResult(op)
        if rc or result.get('status') != 'OK':
            print(f'No data returned for {op}. Try to increase timeout')
            break

        page = result.get('result', [])
        for item in page:
            ref = item.get('reference')
            if ref:
                jobs[ref] = item

        if len(page) < page_size:
            break
        offset += 1

    return jobs


def _fetch_jobs(engine_obj, from_ts, to_ts, state, target_refs, add_events):
    merged = {}
    if target_refs:
        for target in sorted(target_refs):
            merged.update(_fetch_jobs_for_target(engine_obj, target, from_ts, to_ts, state, add_events))
    else:
        merged.update(_fetch_jobs_for_target(engine_obj, None, from_ts, to_ts, state, add_events))
    return merged


def _job_sort_key(jobref):
    tail = str(jobref).split('-')[-1]
    if tail.isdigit():
        return (0, int(tail))
    return (1, str(jobref))


def _write_to_dir(output, fmt, nohead, name, path, unique):
    if not os.path.isdir(path):
        print(f'Path {path} is not a directory')
        return 1
    if not os.access(path, os.W_OK):
        print(f'Path {path} is not writtable')
        return 1

    filename = name
    if unique:
        datestring = datetime.now().strftime('%Y%m%d-%H-%M-%S')
        filename = f'{name}-{datestring}'

    if fmt and fmt.lower() == 'csv':
        filename += '.csv'
    elif fmt and fmt.lower() == 'json':
        filename += '.json'
    else:
        filename += '.txt'

    fullname = os.path.join(path, filename)
    try:
        with open(fullname, 'w', encoding='utf-8') as fd:
            toolkit_helpers.print_output(output, fmt, nohead, fd)
        print(f'Data exported into {fullname}')
        return 0
    except Exception:
        print(f"Can't create a output file {fullname}")
        return 1


def main(argv):
    args = parse_args(argv)
    if args.version:
        print(toolkit_helpers.version)
        return 0

    if args.all and args.dx_host:
        print('Option all (-all) and engine (-d|engine) are mutually exclusive')
        return 1

    if args.state and str(args.state).upper() not in ('COMPLETED', 'FAILED', 'RUNNING', 'SUSPENDED', 'CANCELED'):
        print('Option state can have only COMPLETED, WAITING and FAILED value')
        return 1

    if not toolkit_helpers.ensure_config_file(args.config_file):
        return 1

    engine_obj = Engine(args.dever, args.debug)
    try:
        engine_obj.load_config(args.config_file)
    except Exception as exc:
        print(f'ERROR: failed to load config: {exc}')
        return 1

    engine_list = toolkit_helpers.get_engine_list(args.all, args.dx_host, engine_obj)

    output = Formater(args.debug)
    if args.errDetails:
        output.addHeader(
            {'Appliance': 20},
            {'Job ref  ': 15},
            {'Target name': 20},
            {'Username': 20},
            {'Start date': 30},
            {'End date': 30},
            {'Run time': 10},
            {'State': 12},
            {'Type': 20},
            {'Error Details': 500},
        )
    else:
        output.addHeader(
            {'Appliance': 20},
            {'Job ref  ': 15},
            {'Target name': 20},
            {'Username': 20},
            {'Start date': 30},
            {'End date': 30},
            {'Run time': 10},
            {'State': 12},
            {'Type': 20},
        )

    ret = 0

    for engine in sorted(engine_list):
        if engine_obj.dlpx_connect(engine):
            print(f"Can't connect to Dephix Engine {args.dx_host}\n")
            ret += 1
            continue

        databases = Databases(engine_obj, args.debug)
        groups = GroupObj(engine_obj, args.debug)
        db_map = _db_display_map(databases, groups)

        db_list = None
        if any([args.dbname, args.host, args.group, args.jtype, args.dsource]):
            db_list = toolkit_helpers.get_dblist_from_filter(
                args.jtype,
                args.group,
                args.host,
                args.dbname,
                databases,
                groups,
                debug=args.debug,
                dsource=args.dsource,
            )
            if not db_list:
                print('Object not found. Skipping jobs')
                ret += 1
                continue

        st_timestamp = _ts_for_api(args.st, engine_obj, default_7_days=True)
        if st_timestamp is None:
            print('Wrong start time (st) format')
            return 1

        et_timestamp = None
        if args.et is not None:
            et_timestamp = _ts_for_api(args.et, engine_obj, default_7_days=False)
            if et_timestamp is None:
                print('Wrong end time (et) format')
                return 1

        if args.jobref:
            op = f'resources/json/delphix/job/{args.jobref}'
            result, _fmt, rc = engine_obj.getJSONResult(op)
            jobs_by_ref = {}
            if not rc and result.get('status') == 'OK':
                j = result.get('result', {})
                if j:
                    jobs_by_ref[args.jobref] = j
            else:
                print(f'No data returned for {op}. Try to increase timeout')
                ret += 1
                continue
        else:
            jobs_by_ref = _fetch_jobs(
                engine_obj,
                st_timestamp,
                et_timestamp,
                args.state,
                db_list,
                args.errDetails,
            )

        users = _collect_users(engine_obj)
        timezone = engine_obj.getTimezone()

        for jobref in sorted(jobs_by_ref.keys(), key=_job_sort_key):
            job = jobs_by_ref[jobref]

            if args.state and str(job.get('jobState', '')).upper() != str(args.state).upper():
                continue
            if not _matches_type(job, args.jtype):
                continue

            userref = job.get('user')
            username = users.get(userref, 'N/A') if userref else 'N/A'

            target_ref = job.get('target')
            target_name = db_map.get(target_ref) or job.get('targetName') or ''

            start_ts = job.get('startTime')
            end_ts = job.get('updateTime')
            runtime = _runtime_hms(start_ts, end_ts)

            base_cols = [
                engine,
                jobref,
                target_name,
                username,
                _format_time_with_tz(start_ts, timezone),
                _format_time_with_tz(end_ts, timezone),
                runtime,
                job.get('jobState') or '',
                job.get('actionType') or '',
            ]

            if args.errDetails:
                errmsg = ''
                if str(job.get('jobState') or '') != 'COMPLETED':
                    events = job.get('events') or []
                    if events:
                        errmsg = (events[-1] or {}).get('messageDetails') or ''
                base_cols.append(errmsg)

            output.addLine(*base_cols)

    if args.outdir:
        rc = _write_to_dir(output, args.fmt, args.nohead, 'jobs', args.outdir, True)
        if rc:
            return 1
    else:
        toolkit_helpers.print_output(output, args.fmt, args.nohead)

    return ret


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
