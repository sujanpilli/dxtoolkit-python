#!/usr/bin/env python3
"""Convert analytics raw JSON files produced earlier into raw+aggregated CSVs.

Usage: run from repo root where raw JSON files are located.
"""
import json
import os
import glob

RAW_PATTERN = "*-analytics-*-raw.json"

def write_csv(path, header, rows):
    with open(path, 'w') as fh:
        fh.write(','.join(header) + '\n')
        for r in rows:
            fh.write(','.join(str(x) for x in r) + '\n')


def process_cpu(result):
    # raw: timestamp,idle,kernel,user
    raw_rows = []
    agg_rows = []
    streams = result.get('datapointStreams', [])
    for ds in streams:
        for dp in ds.get('datapoints', []):
            ts = dp.get('timestamp')
            idle = dp.get('idle', '')
            kernel = dp.get('kernel', '')
            user = dp.get('user', '')
            raw_rows.append([ts, idle, kernel, user])
            try:
                ttl = (idle or 0) + (user or 0) + (kernel or 0)
                util = 0 if ttl == 0 else ((user + kernel) / ttl * 100)
            except Exception:
                util = ''
            agg_rows.append([ts, f"{util:.2f}" if isinstance(util, float) else util])
    return (['timestamp','idle','kernel','user'], raw_rows, ['timestamp','utilization'], agg_rows)


def process_network(result):
    raw_rows = []
    agg_map = {}
    streams = result.get('datapointStreams', [])
    for ds in streams:
        iface = ds.get('interface') or ds.get('networkInterface') or 'none'
        client = ds.get('client', 'none')
        for dp in ds.get('datapoints', []):
            ts = dp.get('timestamp')
            inBytes = dp.get('inBytes', 0)
            outBytes = dp.get('outBytes', 0)
            inPackets = dp.get('inPackets', 0)
            outPackets = dp.get('outPackets', 0)
            raw_rows.append([ts, iface, client, inBytes, outBytes, inPackets, outPackets])
            key = (ts, iface, client)
            s = agg_map.setdefault(key, [0,0,0,0])
            s[0] += inBytes
            s[1] += outBytes
            s[2] += inPackets
            s[3] += outPackets
    agg_rows = []
    for (ts, iface, client), vals in sorted(agg_map.items()):
        inMB = vals[0] / (1024*1024)
        outMB = vals[1] / (1024*1024)
        agg_rows.append([ts, iface, client, f"{inMB:.2f}", f"{outMB:.2f}", vals[2], vals[3]])
    return (['timestamp','interface','client','inBytes','outBytes','inPackets','outPackets'], raw_rows,
            ['timestamp','interface','client','bytes_in_MB','bytes_out_MB','packets_in','packets_out'], agg_rows)


def process_generic(result):
    # fallback: flatten datapointStreams into raw csv of timestamp + keys
    raw_rows = []
    keys = set()
    for ds in result.get('datapointStreams', []):
        for dp in ds.get('datapoints', []):
            ts = dp.get('timestamp')
            row = {'timestamp': ts}
            for k, v in dp.items():
                if k == 'timestamp':
                    continue
                row[k] = v
                keys.add(k)
            raw_rows.append(row)
    header = ['timestamp'] + sorted(keys)
    rows = []
    for r in raw_rows:
        rows.append([r.get(h, '') for h in header])
    # aggregated: sum numeric columns per timestamp
    agg_map = {}
    for r in raw_rows:
        ts = r.get('timestamp')
        acc = agg_map.setdefault(ts, {})
        for k, v in r.items():
            if k == 'timestamp':
                continue
            try:
                acc[k] = acc.get(k, 0) + (v or 0)
            except Exception:
                pass
    agg_header = ['timestamp'] + sorted(keys)
    agg_rows = []
    for ts in sorted(agg_map.keys()):
        row = [ts]
        for k in sorted(keys):
            row.append(agg_map[ts].get(k, ''))
        agg_rows.append(row)
    return (header, rows, agg_header, agg_rows)


def convert_file(path):
    base = os.path.basename(path)
    # pattern: <engine>-analytics-<name>-raw.json or similar
    parts = base.split('-analytics-')
    if len(parts) != 2:
        print('Skipping unknown file:', base)
        return
    engine = parts[0]
    rest = parts[1]
    name = rest.replace('-raw.json', '').replace('-raw.csv', '')
    with open(path) as fh:
        data = json.load(fh)
    # data may be top-level result or { 'result': {...} }
    if 'datapointStreams' in data:
        result = data
    elif isinstance(data, dict) and 'result' in data:
        result = data['result']
    else:
        result = data

    if name.endswith('cpu') or name.endswith('default.cpu'):
        header, raw_rows, agg_header, agg_rows = process_cpu(result)
    elif name.endswith('network') or name.endswith('default.network'):
        header, raw_rows, agg_header, agg_rows = process_network(result)
    else:
        header, raw_rows, agg_header, agg_rows = process_generic(result)

    raw_csv = f"{engine}-analytics-{name}-raw.csv"
    agg_csv = f"{engine}-analytics-{name}-aggregated.csv"
    write_csv(raw_csv, header, raw_rows)
    write_csv(agg_csv, agg_header, agg_rows)
    print(f'Wrote {raw_csv} and {agg_csv}')


if __name__ == '__main__':
    files = glob.glob(RAW_PATTERN)
    if not files:
        print('No raw JSON files found matching', RAW_PATTERN)
    for f in files:
        try:
            convert_file(f)
        except Exception as e:
            print('Error converting', f, e)
