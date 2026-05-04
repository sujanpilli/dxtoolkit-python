#!/usr/bin/env python3
"""
Simple mock Delphix Engine HTTP server for testing dx_ctl_analytics.py
Implements minimal endpoints used by the Python port:
- GET /resources/json/delphix/about
- POST/GET /resources/json/delphix/session
- POST /resources/json/delphix/login
- GET /resources/json/delphix/analytics
- GET /resources/json/delphix/analytics/<ref>
- POST endpoints for analytics actions (delete/pause/resume/create)
- POST /sso/virtualization/api/login and /virtualization/api/oauth2-login (token login)

Run: python3 tools/mock_delphix_server.py 8000
"""
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

ANALYTICS = [
    {
        "name": "cpu",
        "reference": "analytic/cpu",
        "type": "Statistic",
        "collectionAxes": ["usage"],
        "collectionInterval": 1,
        "statisticType": "CPU"
    },
    {
        "name": "network",
        "reference": "analytic/network",
        "type": "Statistic",
        "collectionAxes": ["tx","rx"],
        "collectionInterval": 1,
        "statisticType": "NETWORK"
    }
]

class MockHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, code=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path
        # analytics getData
        if path.startswith('/resources/json/delphix/analytics/') and path.endswith('/getData'):
            # return sample datapointStreams
            # extract ref
            parts = path.split('/')
            ref = parts[-2]
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            t1 = (now - timedelta(minutes=2)).isoformat() + 'Z'
            t2 = now.isoformat() + 'Z'
            if ref in ('analytic', 'analytic'):  # generic
                datapointStreams = [
                    {
                        "op": "read",
                        "client": "client1",
                        "device": "dev1",
                        "cached": False,
                        "datapoints": [
                            {"timestamp": t1, "read": {"throughput": 1048576, "count": 10, "latency": {"buckets": [100,200,300]}}},
                            {"timestamp": t2, "read": {"throughput": 2097152, "count": 20, "latency": {"buckets": [150,250,350]}}}
                        ]
                    }
                ]
            else:
                datapointStreams = [
                    {
                        "op": None,
                        "client": "none",
                        "device": "none",
                        "cached": False,
                        "datapoints": [
                            {"timestamp": t1, "usage": 0.12},
                            {"timestamp": t2, "usage": 0.22}
                        ]
                    }
                ]
            resp = {"status": "OK", "result": {"datapointStreams": datapointStreams}}
            return self._send_json(resp)
        # about
        if path == '/resources/json/delphix/about':
            resp = {"status": "OK", "result": {"apiVersion": {"major": 1, "minor": 6, "micro": 0}}}
            return self._send_json(resp)
        # session GET
        if path == '/resources/json/delphix/session':
            resp = {"status": "OK", "result": {"version": {"major": 1, "minor": 6, "micro": 0}}}
            return self._send_json(resp)
        # analytics list
        if path == '/resources/json/delphix/analytics':
            resp = {"status": "OK", "result": ANALYTICS}
            return self._send_json(resp)
        # analytic detail
        if path.startswith('/resources/json/delphix/analytics/'):
            ref = path.split('/')[-1]
            # find by reference ending
            for a in ANALYTICS:
                if a['reference'].endswith(ref) or a['name'] == ref:
                    return self._send_json({"status": "OK", "result": {"state": "running", "reference": a['reference']}})
            return self._send_json({"status": "ERROR", "error": "Not found"}, code=404)
        # default
        self._send_json({"status": "ERROR", "error": "unknown GET"}, code=404)

    def do_POST(self):
        p = urlparse(self.path)
        path = p.path
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else ''
        # session create
        if path == '/resources/json/delphix/session':
            try:
                j = json.loads(body) if body else {}
            except Exception:
                j = {}
            return self._send_json({"status": "OK", "result": j})
        # login
        if path == '/resources/json/delphix/login':
            return self._send_json({"status": "OK", "result": {"name": "admin"}})
        # token login endpoints
        if path == '/sso/virtualization/api/login' or path == '/virtualization/api/oauth2-login':
            return self._send_json({"status": "OK", "result": {"token": "mock"}})
        # analytics create/post actions
        if path == '/resources/json/delphix/analytics':
            # create new analytic
            return self._send_json({"status": "OK", "result": {"reference": "analytic/new"}})
        if path.startswith('/resources/json/delphix/analytics/'):
            # delete/pause/resume
            parts = path.split('/')
            action = parts[-1]
            if action in ('delete', 'pause', 'resume'):
                return self._send_json({"status": "OK", "result": {"action": action}})
        # logout
        if path == '/resources/json/delphix/logout':
            return self._send_json({"status": "OK", "result": {}})
        return self._send_json({"status": "ERROR", "error": "unknown POST"}, code=404)

    def log_message(self, format, *args):
        # reduce console noise
        sys.stdout.write("[mock] %s - - %s\n" % (self.address_string(), format%args))

if __name__ == '__main__':
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except Exception:
            pass
    server = HTTPServer(('0.0.0.0', port), MockHandler)
    print(f"Mock Delphix server listening on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down mock server")
        server.server_close()
