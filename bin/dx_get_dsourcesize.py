#!/usr/bin/env python3
"""Python port of dx_get_dsourcesize.pl."""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'lib', 'py'))

from engine import Engine
from databases import Databases
from group_obj import GroupObj
from formater import Formater
import toolkit_helpers


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Get dSource size for ingestion model')
    parser.add_argument('-d', '--engine', dest='dx_host')
    parser.add_argument('-all', action='store_true')
    parser.add_argument('-name', dest='dbname')
    parser.add_argument('-format', dest='fmt')
    parser.add_argument('-group', dest='group')
    parser.add_argument('-host', dest='host')
    parser.add_argument('-license', action='store_true')
    parser.add_argument('-envname', dest='envname')
    parser.add_argument('-debug', dest='debug', type=int, nargs='?', const=1)
    parser.add_argument('-dever', dest='dever')
    parser.add_argument('-output_unit', dest='output_unit', nargs='?', const='G', default='G')
    parser.add_argument('-version', action='store_true')
    parser.add_argument('-nohead', action='store_true')
    parser.add_argument('-configfile', '-c', dest='config_file')
    return parser.parse_args(argv)


def _ver_tuple(ver):
    try:
        return tuple(int(x) for x in str(ver).split('.'))
    except Exception:
        return (0,)


def _db_runtime_size(dbobj):
    if not isinstance(dbobj, dict):
        return None
    if dbobj.get('runtimeSize') is not None:
        return dbobj.get('runtimeSize')
    runtime = dbobj.get('runtime') or {}
    if runtime.get('databaseSize') is not None:
        return runtime.get('databaseSize')
    if runtime.get('runtimeSize') is not None:
        return runtime.get('runtimeSize')
    return None


def _fetch_ref(engine_obj, endpoint, ref_value, cache):
    if not ref_value:
        return None
    cache_key = f'{endpoint}:{ref_value}'
    if cache_key in cache:
        return cache[cache_key]
    op = f'resources/json/delphix/{endpoint}/{ref_value}'
    result, _fmt, rc = engine_obj.getJSONResult(op)
    value = result.get('result') if not rc and result.get('status') == 'OK' else None
    cache[cache_key] = value
    return value


def _fetch_source_for_database(engine_obj, dbref, cache):
    cache_key = f'source-for-db:{dbref}'
    if cache_key in cache:
        return cache[cache_key]
    op = f'resources/json/delphix/source?database={dbref}'
    result, _fmt, rc = engine_obj.getJSONResult(op)
    value = None
    if not rc and result.get('status') == 'OK':
        res = result.get('result', [])
        if res:
            value = res[0]
    cache[cache_key] = value
    return value


def _source_runtime_status(source_obj):
    runtime = (source_obj or {}).get('runtime') or {}
    return runtime.get('status') or 'NA'


def _source_runtime_size_gb(source_obj):
    runtime = (source_obj or {}).get('runtime') or {}
    size = runtime.get('databaseSize')
    if size is None:
        return 'NA'
    return float(size) / 1024 / 1024 / 1024


def _source_config_ref(source_obj):
    source_type = (source_obj or {}).get('type')
    sync_strategy = (source_obj or {}).get('syncStrategy') or {}
    if source_type in ('MSSqlLinkedSource', 'OracleLinkedSource') and sync_strategy.get('config'):
        return sync_strategy.get('config')
    return (source_obj or {}).get('config')


def _staging_source_ref(source_obj):
    sync_strategy = (source_obj or {}).get('syncStrategy') or {}
    if sync_strategy.get('type') == 'OracleStagingPushSyncStrategy' and sync_strategy.get('stagingSource'):
        return sync_strategy.get('stagingSource')
    return (source_obj or {}).get('stagingSource')


def _source_enabled(source_obj, dbobj):
    if dbobj.get('namespace'):
        return 'N/A'
    runtime = (source_obj or {}).get('runtime') or {}
    if runtime.get('enabled') is not None:
        return 'enabled' if str(runtime.get('enabled')) == 'ENABLED' else 'disabled'
    if (source_obj or {}).get('enabled') is not None:
        return 'enabled' if source_obj.get('enabled') else 'disabled'
    return 'N/A'


def _environment_name_for_source(engine_obj, source_obj, cache):
    config_ref = _source_config_ref(source_obj)
    config = _fetch_ref(engine_obj, 'sourceconfig', config_ref, cache)
    repository_ref = (config or {}).get('repository')
    repository = _fetch_ref(engine_obj, 'repository', repository_ref, cache)
    environment_ref = (repository or {}).get('environment')
    environment = _fetch_ref(engine_obj, 'environment', environment_ref, cache)
    return (environment or {}).get('name')


def _resolve_dsourcesize_fields(engine_obj, dbref, dbobj, cache):
    if dbobj.get('namespace'):
        return {
            'env_name': 'N/A',
            'size_gb': 'N/A',
            'status': 'NA',
            'enabled': 'N/A',
        }

    source_obj = _fetch_source_for_database(engine_obj, dbref, cache)
    env_name = _environment_name_for_source(engine_obj, source_obj, cache)

    if not env_name:
        staging_ref = _staging_source_ref(source_obj)
        staging_source = _fetch_ref(engine_obj, 'source', staging_ref, cache)
        env_name = _environment_name_for_source(engine_obj, staging_source, cache)

    return {
        'env_name': env_name or 'NA',
        'size_gb': _source_runtime_size_gb(source_obj),
        'status': _source_runtime_status(source_obj),
        'enabled': _source_enabled(source_obj, dbobj),
    }


def _db_runtime_status(dbobj):
    if not isinstance(dbobj, dict):
        return 'N/A'
    if dbobj.get('runtimeStatus') is not None:
        return dbobj.get('runtimeStatus')
    runtime = dbobj.get('runtime') or {}
    if runtime.get('status') is not None:
        return runtime.get('status')
    return 'N/A'


def _db_enabled(dbobj):
    if not isinstance(dbobj, dict):
        return 'N/A'
    val = dbobj.get('enabled')
    if val is None:
        runtime = dbobj.get('runtime') or {}
        val = runtime.get('enabled')
    if val is None:
        return 'N/A'
    if isinstance(val, bool):
        return 'true' if val else 'false'
    return str(val)


def _is_dsource(dbobj):
    if not isinstance(dbobj, dict):
        return False
    return not bool(dbobj.get('provisionContainer'))


def _passes_filters(dbref, databases, groups, args):
    dbobj = databases.getDB(dbref)
    if not dbobj:
        return False

    if args.group:
        grp = groups.getGroupByName(args.group)
        if not grp or dbobj.get('group') != grp.get('reference'):
            return False

    if args.dbname:
        allowed = {x.strip() for x in str(args.dbname).split(',') if x.strip()}
        if databases.getName(dbref) not in allowed:
            return False

    if args.host:
        if str(dbobj.get('host', '')) != str(args.host):
            return False

    if args.envname:
        env = dbobj.get('environmentName') or dbobj.get('stagingEnvironmentName')
        if str(env or '') != str(args.envname):
            return False

    return True


def _get_license_usage(engine_obj):
    op = 'resources/json/delphix/usage/aggregateIngestedSize'
    result, _fmt, rc = engine_obj.getJSONResult(op)
    if rc or result.get('status') != 'OK':
        print(f'No data returned for {op}. Try to increase timeout')
        return None

    out = {'total': result.get('result', {}).get('aggregateIngestedSize'), 'databases': []}
    for db in result.get('result', {}).get('sourceIngestionData', []):
        ctype = str(db.get('containerType', ''))
        ctype = ctype.replace('_DB_CONTAINER', '')
        out['databases'].append(
            {
                'timestamp': db.get('timestamp'),
                'name': db.get('sourceName'),
                'type': ctype,
                'size': db.get('ingestedSize'),
            }
        )
    return out


def main(argv):
    args = parse_args(argv)
    if args.version:
        print(toolkit_helpers.version)
        return 0

    if args.all and args.dx_host:
        print('Option all (-all) and engine (-d|engine) are mutually exclusive')
        return 1

    unit = str(args.output_unit or 'G').upper()
    if unit not in ('K', 'M', 'G', 'T'):
        print('Option -output_unit can be only K for KB, M for MB, G for GB and T for TB')
        return 1

    if not toolkit_helpers.ensure_config_file(args.config_file):
        return 1

    eng = Engine(args.dever, args.debug)
    try:
        eng.load_config(args.config_file)
    except Exception as exc:
        print(f'ERROR: failed to load config: {exc}')
        return 1

    engine_list = toolkit_helpers.get_engine_list(args.all, args.dx_host, eng)
    output = Formater(args.debug)

    if args.license:
        output.addHeader(
            {'Appliance': 10},
            {'Type': 40},
            {'Database': 40},
            {toolkit_helpers.get_unit('Size', unit): 30},
            {'Timestamp': 30},
        )
    else:
        output.addHeader(
            {'Appliance': 10},
            {'Env name': 20},
            {'Group': 15},
            {'Database': 30},
            {toolkit_helpers.get_unit('Size', unit): 30},
            {'Status': 30},
            {'Enabled': 30},
        )

    ret = 0

    print('# Delphix can automatically calculate the usage for Oracle, SQL Server and ASE databases for each Delphix Engine.')
    print('# For other databases, and before the source is connected to the Delphix Engine')
    print('# you will need to run a query on the source system for the relevant data.')

    for engine_name in sorted(engine_list):
        if eng.dlpx_connect(engine_name):
            print(f"Can't connect to Dephix Engine {engine_name}\n")
            ret += 1
            continue

        cache = {}

        if args.license:
            if _ver_tuple(eng.getApi()) < _ver_tuple('1.10.3'):
                print('There is no license API. Results returned by non license API as using method described in CLI method in the Delphix Pricing Guide.')
                print('For details please contact your Delphix account manager')
                return 1

            lic = _get_license_usage(eng)
            if lic is None:
                ret += 1
                continue

            for db in lic.get('databases', []):
                size = db.get('size')
                dbsize = toolkit_helpers.print_size(size, 'B', unit) if size is not None else 'N/A'
                ts = db.get('timestamp')
                timestamp = toolkit_helpers.convert_from_utc(ts, eng.getTimezone()) if ts else 'N/A'
                output.addLine(
                    engine_name,
                    db.get('type'),
                    db.get('name'),
                    dbsize,
                    timestamp,
                )
        else:
            databases = Databases(eng, args.debug)
            groups = GroupObj(eng, args.debug)

            db_list = [dbref for dbref in databases.getDBList() if _is_dsource(databases.getDB(dbref))]
            db_list = [dbref for dbref in db_list if _passes_filters(dbref, databases, groups, args)]

            if not db_list:
                print(f'There is no DB selected to process on {engine_name} . Please check filter definitions.')
                ret += 1
                continue

            for dbref in db_list:
                dbobj = databases.getDB(dbref)
                resolved = _resolve_dsourcesize_fields(eng, dbref, dbobj, cache)
                output.addLine(
                    engine_name,
                    resolved['env_name'],
                    groups.getName(dbobj.get('group')),
                    databases.getName(dbref),
                    toolkit_helpers.print_size(resolved['size_gb'], 'G', unit),
                    resolved['status'],
                    resolved['enabled'],
                )

    toolkit_helpers.print_output(output, args.fmt, args.nohead)
    return ret


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
