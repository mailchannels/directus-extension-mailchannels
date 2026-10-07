"""Exercise the built extension in real Directus; isolated HTTPS fixture, no email.
Run after npm ci && npm run build. Requires Docker, openssl, Python 3.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'directus/directus:12.4.1'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--studio-port', type=int, help='Keep disposable fixture running on localhost for Data Studio review; Ctrl-C cleans up')
args = parser.parse_args()
if args.studio_port is not None and not 1024 <= args.studio_port <= 65535:
    parser.error('Studio port must be1024–65535')

def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()

suffix = secrets.token_hex(5)
network, server, fixture = [f'visibility-directus-{suffix}-{kind}' for kind in ('net', 'app', 'fixture')]
key, token = secrets.token_hex(24), secrets.token_hex(24)
created = []
try:
    with tempfile.TemporaryDirectory(prefix='visibility-directus-') as directory:
        tmp = Path(directory)
        os.chmod(tmp, 0o755)
        ext = tmp / 'extensions' / 'mailchannels'
        ext.mkdir(parents=True)
        shutil.copy(ROOT / 'package.json', ext)
        shutil.copytree(ROOT / 'dist', ext / 'dist')
        cert = tmp / 'certs'
        cert.mkdir()
        run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
            '-keyout', str(cert / 'key.pem'), '-out', str(cert / 'cert.pem'),
            '-subj', '/CN=api.mailchannels.net', '-addext', 'subjectAltName=DNS:api.mailchannels.net')
        env = tmp / 'app.env'
        env.write_text('\n'.join([
            f'SECRET={secrets.token_hex(32)}', 'DB_CLIENT=sqlite3', 'DB_FILENAME=/tmp/directus.db',
            'ADMIN_EMAIL=fixture@example.com', 'ADMIN_PASSWORD=' + ('Local-fixture-only-password-2026' if args.studio_port else secrets.token_hex(24)), f'ADMIN_TOKEN={token}',
            'MAILCHANNELS_API_KEY=' + key, 'FLOWS_ENV_ALLOW_LIST=MAILCHANNELS_API_KEY',
            'NODE_EXTRA_CA_CERTS=/certs/cert.pem', 'IMPORT_IP_DENY_LIST=',
            'TELEMETRY=false', 'EXTENSIONS_MUST_LOAD=true',
        ]))
        os.chmod(env, 0o600)
        fixture_env = tmp / 'fixture.env'
        fixture_env.write_text('FIXTURE_KEY=' + key)
        os.chmod(fixture_env, 0o600)
        run('docker', 'network', 'create', '--internal', network)
        created.append(('network', network))
        run('docker', 'run', '-d', '--name', fixture, '--network', network,
            '--network-alias', 'api.mailchannels.net', '--env-file', str(fixture_env),
            '-v', f'{cert}:/certs:ro', '-v', f'{ROOT / "test/fixture.mjs"}:/fixture.mjs:ro',
            'node:22-bookworm', 'node', '/fixture.mjs')
        created.append(('container', fixture))
        run('docker', 'run', '-d', '--name', server, '--network', network,
            '--env-file', str(env),
            '-v', f'{tmp / "extensions"}:/directus/extensions:ro', '-v', f'{cert}:/certs:ro', IMAGE)
        created.append(('container', server))
        def request(path, method='GET', data=None):
            script = """
              const [path, method, data] = JSON.parse(process.argv[1]);
              fetch('http://127.0.0.1:8055' + path, {
                method,
                headers: {Authorization: 'Bearer ' + process.env.ADMIN_TOKEN, 'Content-Type': 'application/json'},
                body: data === null ? undefined : JSON.stringify(data),
                signal: AbortSignal.timeout(10000)
              }).then(async r => {
                const body = await r.text();
                console.log(JSON.stringify({status: r.status, body}));
              }).catch(() => { console.log(JSON.stringify({status: 0, body: 'Not ready'})); });
            """
            response = json.loads(run('docker', 'exec', server, 'node', '-e', script, json.dumps([path, method, data])))
            if not 200 <= response['status'] < 300:
                raise RuntimeError(str(response['status']) + ' ' + response['body'].replace(key, '[redacted]').replace(token, '[redacted]'))
            return json.loads(response['body'])

        for attempt in range(90):
            try:
                request('/users/me')
                break
            except Exception:
                if attempt == 89:
                    raise RuntimeError('Directus failed to start: ' + run('docker', 'logs', server).replace(key, '[redacted]').replace(token, '[redacted]'))
                time.sleep(1)
        print('Directus ready; built sandbox extension loaded', flush=True)
        flow = request('/flows', 'POST', {
            'name': 'MailChannels fixture', 'status': 'active', 'trigger': 'webhook',
            'accountability': 'all', 'options': {'method': 'POST', 'return': '$last', 'async': False},
        })['data']['id']
        payload = {
            'from': {'email': 'sender@example.com'}, 'subject': 'Fixture only',
            'personalizations': [{'to': [{'email': 'recipient@example.com'}], 'bcc': [{'email': 'bcc@example.com'}]}],
            'content': [{'type': 'text/plain', 'value': 'Hello'}],
            'attachments': [{'filename': 'hello.txt', 'type': 'text/plain', 'content': 'SGVsbG8='}],
        }
        options = {'apiKey': '{{$env.MAILCHANNELS_API_KEY}}', 'payload': payload, 'dryRun': True}
        operation = request('/operations', 'POST', {
            'flow': flow, 'name': 'Email', 'key': 'email', 'type': 'mailchannels-send-email',
            'position_x': 19, 'position_y': 1, 'options': options,
        })['data']['id']
        request('/flows/' + flow, 'PATCH', {'operation': operation})
        def trigger():
            return request('/flows/trigger/' + flow, 'POST', {})
        result = trigger()
        assert result == {'status': 200, 'validated': True, 'accepted': False}, result
        print('Dry-run HTTP 200 through sandbox and TLS fixture: passed', flush=True)
        options['dryRun'] = False
        request('/operations/' + operation, 'PATCH', {'options': options})
        result = trigger()
        assert result == {'status': 202, 'validated': False, 'accepted': True}, result
        print('Send acceptance HTTP 202 against fixture only: passed', flush=True)
        options['payload']['subject'] = 'Reject fixture'
        request('/operations/' + operation, 'PATCH', {'options': options})
        result = trigger()
        assert key not in json.dumps(result)
        assert not result.get('accepted')
        print('401 rejection sanitization: passed', flush=True)
        saved = request('/operations/' + operation)
        revisions = request('/revisions?filter[collection][_eq]=directus_flows&filter[item][_eq]=' + flow)
        executions = [r['data'] for r in revisions['data'] if isinstance(r.get('data'), dict) and r['data'].get('steps')]
        assert len(executions) == 3, 'Expected three recorded Flow executions'
        statuses = []
        for execution in executions:
            step = execution['steps'][0]
            assert step['operation'] == operation
            statuses.append(step['status'])
            redacted = step['options']['apiKey']
            assert redacted and redacted != key and '{{' not in redacted
            assert execution['data']['$env']['MAILCHANNELS_API_KEY'] == redacted
        assert sorted(statuses) == ['reject', 'resolve', 'resolve'], statuses
        serialized = json.dumps(revisions)
        assert key not in json.dumps(saved)
        assert key not in serialized
        assert 'MAILCHANNELS_API_KEY' in serialized, 'Expected redaction evidence missing'
        assert key not in run('docker', 'logs', server)
        print('Saved configuration, flow revisions and container logs contain no credential: passed', flush=True)
        script = "fetch('https://api.mailchannels.net/stats',{dispatcher:undefined}).then(r=>r.text()).then(console.log)"
        stats = json.loads(run('docker', 'exec', '-e', 'NODE_EXTRA_CA_CERTS=/certs/cert.pem', fixture, 'node', '-e', script))
        assert len(stats) == 3, stats
        assert all(call['authorized'] for call in stats)
        assert stats[0]['url'].endswith('?dry-run=true')
        assert stats[0]['payload']['attachments'] == payload['attachments']
        assert len(stats[0]['payload']['personalizations'][0]['bcc']) == 1
        print('Exactly three authenticated fixture requests; payload preserved; no retries: passed', flush=True)
        print(json.dumps({'directus': '12.4.1', 'checks': 6, 'live_email_sent': False, 'external_network': False}))
        if args.studio_port:
            from studio_tunnel import open_tunnel
            tunnel = open_tunnel(server, args.studio_port)
            options['dryRun'] = True
            options['payload']['subject'] = 'Studio fixture only'
            request('/operations/' + operation, 'PATCH', {'options': options})
            print(json.dumps({'studio': f'http://127.0.0.1:{args.studio_port}/admin/settings/flows/{flow}',
                              'synthetic_login': 'fixture@example.com', 'cleanup': 'Ctrl-C this process'}), flush=True)
            try:
                while True: time.sleep(1)
            except KeyboardInterrupt:
                print('Stopping disposable Studio fixture', flush=True)
            finally:
                tunnel.shutdown(); tunnel.server_close()

finally:
    for kind, name in reversed(created):
        subprocess.run(['docker', 'rm', '-fv', name] if kind == 'container' else ['docker', 'network', 'rm', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
