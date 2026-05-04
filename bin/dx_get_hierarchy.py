#!/usr/bin/env python3
"""Python port of dx_get_hierarchy.pl."""
import argparse
import os
import sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'lib', 'py'))

from engine import Engine
from databases import Databases
from group_obj import GroupObj
from formater import Formater
import toolkit_helpers


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Get database hierarchy')
    parser.add_argument('-d', '--engine', dest='dx_host')
    parser.add_argument('-name', dest='dbname')
    parser.add_argument('-format', dest='fmt')
    parser.add_argument('-type', dest='dbtype')
    parser.add_argument('-group', dest='group')
    parser.add_argument('-host', dest='host')
    parser.add_argument('-dsource', dest='dsource')
    parser.add_argument('-primary', action='store_true')
    parser.add_argument('-envname', dest='envname')
    parser.add_argument('-instance', dest='instance', type=int)
    parser.add_argument('-instancename', dest='instancename')
    parser.add_argument('-reponame', dest='repositoryname')
    parser.add_argument('-parent_engine', dest='parent_engine')
    parser.add_argument('-printhierarchy', dest='printhierarchy', nargs='?', const='')
    parser.add_argument('-debug', dest='debug', type=int, nargs='?', const=1)
    parser.add_argument('-dever', dest='dever')
    parser.add_argument('-all', action='store_true')
    parser.add_argument('-version', action='store_true')
    parser.add_argument('-nohead', action='store_true')
    parser.add_argument('-configfile', '-c', dest='config_file')
    return parser.parse_args(argv)


def _strip_local_suffix(ref):
    if isinstance(ref, str) and ref.endswith('@l'):
        return ref[:-2]
    return ref


def _db_type(db):
    if not isinstance(db, dict):
        return 'N/A'
    if db.get('provisionContainer'):
        return 'VDB'
    dtype = str(db.get('type', ''))
    if 'detached' in dtype.lower():
        return 'detached'
    return 'dSource'


def _db_name(databases, dbref):
    name = databases.getName(dbref)
    return name if name is not None else dbref


def _get_parent_container(db):
    if not isinstance(db, dict):
        return ''
    return db.get('provisionContainer') or db.get('parent') or ''


def _get_source_config_name(db):
    if not isinstance(db, dict):
        return 'N/A'
    for key in ('sourceConfigName', 'sourceName', 'sourceConfig'):
        if db.get(key):
            return db.get(key)
    runtime = db.get('runtime') or {}
    for key in ('sourceConfigName', 'sourceName'):
        if runtime.get(key):
            return runtime.get(key)
    return 'N/A'


def _is_replica(db):
    if not isinstance(db, dict):
        return False
    return bool(db.get('namespace'))


def _get_current_timeflow(db):
    if not isinstance(db, dict):
        return None
    return db.get('currentTimeflow')


def _get_parent_name(databases, dbref):
    db = databases.getDB(dbref)
    if not db:
        return None
    pref = _get_parent_container(db)
    if not pref:
        return None
    return _db_name(databases, pref)


def _load_timeflows(engine_obj):
    op = 'resources/json/delphix/timeflow'
    result, _fmt, rc = engine_obj.getJSONResult(op)
    tfs = {}
    if rc or result.get('status') != 'OK':
        print(f'No data returned for {op}. Try to increase timeout')
        return tfs
    for item in result.get('result', []):
        ref = item.get('reference')
        if ref:
            tfs[ref] = item
    return tfs


def _load_snapshots_for_dbs(engine_obj, dbrefs):
    snaps = {}
    for dbref in dbrefs:
        op = f'resources/json/delphix/snapshot?database={dbref}'
        result, _fmt, rc = engine_obj.getJSONResult(op)
        if rc or result.get('status') != 'OK':
            continue
        for item in result.get('result', []):
            ref = item.get('reference')
            if ref:
                snaps[ref] = item
    return snaps


def _get_latest_change_point(snaps, snapref):
    snap = snaps.get(snapref, {})
    lcp = snap.get('latestChangePoint') or {}
    return lcp.get('location', 'N/A')


def _get_snapshot_timezone(snaps, snapref):
    snap = snaps.get(snapref)
    if not snap:
        return 'N/A'
    tz = snap.get('timezone')
    if not tz:
        return 'N/A'
    return str(tz).split(',')[0]


def _get_snapshot_time_with_timezone(snaps, snapref):
    snap = snaps.get(snapref)
    if not snap:
        return ('N/A', 'N/A')
    lcp = snap.get('latestChangePoint') or {}
    ts = lcp.get('timestamp')
    if not ts:
        return ('N/A', 'N/A')
    tz = _get_snapshot_timezone(snaps, snapref)
    if tz == 'N/A':
        return ('N/A - timezone unknown', 'N/A')
    return (toolkit_helpers.convert_from_utc(ts, tz, 1), tz)


def _tf_get_parent(tf):
    pp = (tf or {}).get('parentPoint') or {}
    if not pp:
        return ''
    if pp.get('timeflow'):
        return pp.get('timeflow')
    return 'deleted'


def _tf_get_parent_snapshot(tf):
    return (tf or {}).get('parentSnapshot') or ''


def _tf_get_parent_timestamp(tf):
    pp = (tf or {}).get('parentPoint') or {}
    return pp.get('timestamp')


def _tf_get_parent_location(tf):
    pp = (tf or {}).get('parentPoint') or {}
    return pp.get('location')


def _tf_get_container(tf):
    return (tf or {}).get('container')


def _tf_is_replica(tf):
    return bool((tf or {}).get('namespace'))


def _tf_generate_hierarchy(local_tfs, remote_map, local_databases, parent_tfs=None):
    hier = {}
    for tfref, tf in local_tfs.items():
        parent_ref = _tf_get_parent(tf)
        if parent_ref == '':
            if _tf_is_replica(tf):
                dbcont = _tf_get_container(tf)
                dbobj = local_databases.getDB(dbcont)
                if _db_type(dbobj) == 'VDB':
                    if remote_map and tfref in remote_map:
                        parent_ref = remote_map[tfref]
                    else:
                        parent_ref = 'notlocal'
        else:
            parent_ref = f'{parent_ref}@l'

        hier[f'{tfref}@l'] = {'parent': parent_ref, 'source': 'l'}

    if parent_tfs:
        for tfref, tf in parent_tfs.items():
            hier[tfref] = {'parent': _tf_get_parent(tf), 'source': 'p'}

    return hier


def _db_generate_hierarchy(local_dbs, remote_map, parent_dbs=None):
    hier = {}
    for dbref in local_dbs.getDBList():
        db = local_dbs.getDB(dbref)
        parent_ref = _get_parent_container(db)
        if parent_ref == '':
            if _db_type(db) == 'VDB':
                if _is_replica(db):
                    if remote_map and dbref in remote_map:
                        parent_ref = remote_map[dbref]
                    else:
                        parent_ref = 'notlocal'
                else:
                    parent_ref = 'deleted'
        else:
            parent_ref = f'{parent_ref}@l'

        hier[f'{dbref}@l'] = {'parent': parent_ref, 'source': 'l'}

    if parent_dbs:
        for dbref in parent_dbs.getDBList():
            db = parent_dbs.getDB(dbref)
            hier[dbref] = {'parent': _get_parent_container(db), 'source': 'p'}

    return hier


def _tf_find_dsource(tfref, hier, local_tfs):
    local_ref = f'{tfref}@l'
    child = None
    parent = None
    while True:
        item = hier.get(local_ref)
        if not item:
            return ('deleted', None)
        parent = item.get('parent')
        if parent is None:
            parent = 'deleted'
        clean_parent = _strip_local_suffix(parent)
        stop = False
        if parent not in ('', 'deleted', 'notlocal'):
            ptf = local_tfs.get(clean_parent, {})
            if str(ptf.get('creationType', '')) == 'SOURCE_CONTINUITY':
                stop = True
        if parent in ('', 'deleted', 'notlocal') or stop:
            break
        child = local_ref
        local_ref = parent

    if parent == 'deleted':
        return ('deleted', None)
    if parent == 'notlocal':
        return ('notlocal', None)
    return (local_ref, child)


def _db_find_dsource(dbref, hier):
    local_ref = f'{dbref}@l'
    child = None
    while True:
        item = hier.get(local_ref)
        if not item:
            return ('deleted', None)
        parent = item.get('parent')
        if parent is None:
            return ('deleted', None)
        if parent in ('', 'deleted', 'notlocal'):
            if parent == 'deleted':
                return ('deleted', None)
            if parent == 'notlocal':
                return ('notlocal', None)
            return (local_ref, child)
        child = local_ref
        local_ref = parent


def _db_return_hierarchy(dbref, hier):
    local_ref = f'{dbref}@l'
    ret = []
    while True:
        item = hier.get(local_ref)
        if not item:
            break
        ret.append({'ref': _strip_local_suffix(local_ref), 'source': item.get('source')})
        parent = item.get('parent')
        if parent in ('', 'deleted', 'notlocal'):
            break
        local_ref = parent
    return ret


def _get_namespace_list(engine_obj):
    op = 'resources/json/delphix/namespace'
    result, _fmt, rc = engine_obj.getJSONResult(op)
    if rc or result.get('status') != 'OK':
        return []
    return result.get('result', [])


def _translate_object(engine_obj, namespace_ref, obj_ref):
    op = f"resources/json/delphix/namespace/{namespace_ref}/translate?object={quote(str(obj_ref), safe='')}"
    result, _fmt, rc = engine_obj.getJSONResult(op)
    if rc or result.get('status') != 'OK':
        return None
    return result.get('result')


def _get_replication_specs(engine_obj):
    op = 'resources/json/delphix/replication/spec'
    result, _fmt, rc = engine_obj.getJSONResult(op)
    if rc or result.get('status') != 'OK':
        return []
    return result.get('result', [])


def _replication_objects(spec):
    ospec = spec.get('objectSpecification') or {}
    otype = ospec.get('type')
    if otype == 'ReplicationList':
        return ospec.get('objects', [])
    if otype == 'ReplicationSecureList':
        return ospec.get('containers', [])
    return spec.get('objects', [])


def _build_replicate_mapping(local_engine, parent_engine, parent_tfs):
    local_ns = _get_namespace_list(local_engine)
    parent_specs = _get_replication_specs(parent_engine)
    mapping = {}

    specs_by_tag = {}
    for spec in parent_specs:
        tag = spec.get('tag')
        if tag:
            specs_by_tag[tag] = spec

    tf_by_container = {}
    for tfref, tf in parent_tfs.items():
        cont = _tf_get_container(tf)
        if cont:
            tf_by_container.setdefault(cont, []).append(tfref)

    for ns in local_ns:
        nsref = ns.get('reference')
        tag = ns.get('tag')
        if not nsref or not tag:
            continue
        spec = specs_by_tag.get(tag)
        if not spec:
            print("Replication profile not found (possibly deleted) - parents for some objects can't be found")
            continue
        for obj in _replication_objects(spec):
            local_obj = _translate_object(local_engine, nsref, obj)
            if local_obj:
                mapping[local_obj] = obj
            for remotetf in tf_by_container.get(obj, []):
                local_tf = _translate_object(local_engine, nsref, remotetf)
                if local_tf:
                    mapping[local_tf] = remotetf

    return mapping


def _passes_filters(dbref, databases, groups, args):
    db = databases.getDB(dbref)
    if not db:
        return False

    if args.dbtype:
        t = _db_type(db).lower()
        if t not in ('vdb', 'dsource'):
            return False
        if t != str(args.dbtype).lower():
            return False

    if args.group:
        grp = groups.getGroupByName(args.group)
        if not grp or db.get('group') != grp.get('reference'):
            return False

    if args.host and str(db.get('host', '')) != str(args.host):
        return False

    if args.dbname:
        names = {x.strip() for x in str(args.dbname).split(',') if x.strip()}
        if databases.getName(dbref) not in names:
            return False

    if args.envname and str(db.get('environmentName') or '') != str(args.envname):
        return False

    if args.primary and _is_replica(db):
        return False

    if args.dsource:
        pname = _get_parent_name(databases, dbref)
        dname = databases.getName(dbref)
        if str(pname or '') != str(args.dsource) and str(dname or '') != str(args.dsource):
            return False

    if args.instance is not None:
        if str(db.get('instance') or '') != str(args.instance):
            return False

    if args.instancename:
        if str(db.get('instanceName') or '') != str(args.instancename):
            return False

    if args.repositoryname:
        if str(db.get('repository') or db.get('repositoryName') or '') != str(args.repositoryname):
            return False

    return True


def main(argv):
    args = parse_args(argv)
    if args.version:
        print(toolkit_helpers.version)
        return 0

    if args.all and args.dx_host:
        print('Option all (-all) and engine (-d|engine) are mutually exclusive')
        return 1

    if args.printhierarchy is not None:
        ph = str(args.printhierarchy).lower()
        if ph not in ('', 'p2c', 'c2p'):
            print(f'Option printhierarchy has a wrong argument - {args.printhierarchy}')
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
    output.addHeader(
        {'Appliance': 10},
        {'Database': 30},
        {'Group': 15},
        {'Type': 8},
        {'dSource': 30},
        {'dS time': 35},
        {'Physical DB': 30},
        {'First child DB': 30},
        {'Parent database': 30},
    )

    ret = 0

    parent_engine_obj = None
    parent_databases = None
    parent_tfs = None
    parent_snaps = None

    if args.parent_engine:
        parent_engine_obj = Engine(args.dever, args.debug)
        try:
            parent_engine_obj.load_config(args.config_file)
        except Exception as exc:
            print(f'ERROR: failed to load config for parent engine: {exc}')
            return 1

        if parent_engine_obj.dlpx_connect(args.parent_engine):
            print(f"Can't connect to Dephix Engine {args.parent_engine}\n")
            return 1

        parent_databases = Databases(parent_engine_obj, args.debug)
        parent_tfs = _load_timeflows(parent_engine_obj)
        parent_snaps = _load_snapshots_for_dbs(parent_engine_obj, parent_databases.getDBList())

    for engine_name in sorted(engine_list):
        if engine_obj.dlpx_connect(engine_name):
            print(f"Can't connect to Dephix Engine {engine_name}\n")
            ret += 1
            continue

        databases = Databases(engine_obj, args.debug)
        groups = GroupObj(engine_obj, args.debug)
        local_tfs = _load_timeflows(engine_obj)

        object_map = {}
        if parent_engine_obj is not None:
            object_map = _build_replicate_mapping(engine_obj, parent_engine_obj, parent_tfs)

        db_list = [dbref for dbref in databases.getDBList() if _passes_filters(dbref, databases, groups, args)]
        if not db_list:
            print(f'There is no DB selected to process on {engine_name} . Please check filter definitions.')
            ret += 1
            continue

        local_snaps = _load_snapshots_for_dbs(engine_obj, databases.getDBList())

        dbs = {'l': databases, 'p': parent_databases}
        tfs = {'l': local_tfs, 'p': parent_tfs}
        snps = {'l': local_snaps, 'p': parent_snaps}

        hier_tf = _tf_generate_hierarchy(local_tfs, object_map, databases, parent_tfs)
        hier_db = _db_generate_hierarchy(databases, object_map, parent_databases)

        for dbref in db_list:
            dbobj = databases.getDB(dbref)
            group_name = groups.getName(dbobj.get('group'))

            if args.printhierarchy is not None:
                arr = _db_return_hierarchy(dbref, hier_db)
                names = []
                for hi in arr:
                    src = hi.get('source')
                    dbset = dbs.get(src)
                    if not dbset:
                        continue
                    names.append(_db_name(dbset, hi.get('ref')))

                if str(args.printhierarchy).lower() == 'p2c':
                    names = list(reversed(names))
                print(f"{engine_name} : {' --> '.join(names)}")
                continue

            snaptime = 'N/A'
            childname = 'N/A'
            physicaldb = 'N/A'
            parentname = ''
            parent1levelname = ''

            if _db_type(dbobj) == 'VDB':
                cur_tf = _get_current_timeflow(dbobj)
                topds, child = _tf_find_dsource(cur_tf, hier_tf, local_tfs) if cur_tf else ('deleted', None)
                topdsc, _childc = _db_find_dsource(dbref, hier_db)

                parent_container = _get_parent_container(dbobj)
                if parent_container:
                    parent1level = databases.getDB(parent_container)
                    parent1levelname = _db_name(databases, parent_container) if parent1level else 'N/A'
                else:
                    parent1levelname = 'N/A'

                if topdsc == 'deleted':
                    parentname = 'parent deleted'
                    physicaldb = 'N/A'
                elif topdsc == 'notlocal':
                    parentname = 'dSource on other DE'
                    physicaldb = 'N/A'
                elif topdsc is not None:
                    clean_topdsc = _strip_local_suffix(topdsc)
                    top_meta = hier_db.get(topdsc, {})
                    src = top_meta.get('source')
                    dbset = dbs.get(src)
                    topdb = dbset.getDB(clean_topdsc) if dbset else None
                    if topdb:
                        parentname = _db_name(dbset, clean_topdsc)
                        if _db_type(topdb) != 'detached':
                            physicaldb = _get_source_config_name(topdb)
                        else:
                            physicaldb = 'detached'
                    else:
                        parentname = 'N/A'
                        physicaldb = 'N/A'
                else:
                    print('no dSource found - error ?')
                    ret += 1
                    continue

                if child:
                    clearchild = _strip_local_suffix(child)
                    top_meta = hier_tf.get(topds, {})
                    child_meta = hier_tf.get(child, {})
                    src_top = top_meta.get('source')
                    src_child = child_meta.get('source')
                    tf_top_set = tfs.get(src_top) or {}
                    tf_child_set = tfs.get(src_child) or {}

                    child_tf = tf_top_set.get(clearchild)
                    childdb_ref = _tf_get_container(child_tf) if child_tf else None
                    child_db_set = dbs.get(src_child)
                    cobj = child_db_set.getDB(childdb_ref) if child_db_set and childdb_ref else None
                    childname = _db_name(child_db_set, childdb_ref) if child_db_set and childdb_ref else 'N/A'

                    dsource_snap = _tf_get_parent_snapshot((tf_child_set or {}).get(clearchild))

                    if dsource_snap and cobj and _db_type(cobj) == 'VDB':
                        timestamp = _tf_get_parent_timestamp((tf_child_set or {}).get(clearchild))
                        loc = _tf_get_parent_location((tf_child_set or {}).get(clearchild))
                        snap_set = snps.get(src_child) or {}
                        lastsnaploc = _get_latest_change_point(snap_set, dsource_snap)

                        if timestamp:
                            timezone = _get_snapshot_timezone(snap_set, dsource_snap)
                            if timezone != 'N/A':
                                st = toolkit_helpers.convert_from_utc(timestamp, timezone, 1)
                                snaptime = st if st is not None else 'N/A'
                            else:
                                snaptime = 'N/A - unknown timezone'
                        elif loc != lastsnaploc:
                            snaptime = loc
                        else:
                            snaptime, _tz = _get_snapshot_time_with_timezone(snap_set, dsource_snap)
                    else:
                        snaptime = 'N/A'
                else:
                    if topdsc == 'notlocal':
                        snaptime = 'N/A'
                    else:
                        snaptime = 'N/A - timeflow deleted'
                    childname = 'N/A'
            else:
                snaptime = 'N/A'
                childname = 'N/A'
                parentname = ''
                parent1levelname = ''
                if _db_type(dbobj) != 'detached':
                    physicaldb = _get_source_config_name(dbobj)
                else:
                    physicaldb = 'detached'

            output.addLine(
                engine_name,
                _db_name(databases, dbref),
                group_name,
                _db_type(dbobj),
                parentname,
                snaptime,
                physicaldb,
                childname,
                parent1levelname,
            )

    if args.printhierarchy is None:
        toolkit_helpers.print_output(output, args.fmt, args.nohead)

    return ret


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
