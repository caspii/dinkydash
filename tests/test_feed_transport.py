"""Exercise DNS pinning and real TLS against an isolated, invented calendar."""

from collections import Counter
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import shutil
import socket
import ssl
import subprocess
from threading import Thread

import pytest
import requests.adapters
import urllib3.util.connection

from dinkydash import calendars
from dinkydash.calendars import FeedError, FeedRefused
from test_feed_safety import ICS

PUBLIC = '1.1.1.1'
PUBLIC_V6 = '2606:4700:4700::1111'


@pytest.fixture(scope='module')
def certificate(tmp_path_factory):
    openssl = shutil.which('openssl')
    if not openssl:
        pytest.skip('openssl is needed to generate a temporary TLS test certificate')
    directory = tmp_path_factory.mktemp('calendar-tls')
    cert, key = directory / 'cert.pem', directory / 'key.pem'
    subprocess.run([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                    '-keyout', str(key), '-out', str(cert), '-days', '1',
                    '-subj', '/CN=calendar.example', '-addext',
                    'subjectAltName=DNS:calendar.example,DNS:next.example'],
                   check=True, capture_output=True)
    return cert, key


@pytest.fixture
def transport(certificate, monkeypatch):
    cert, key = certificate
    seen = {'dns': Counter(), 'connections': [], 'sni': [], 'requests': []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen['requests'].append((self.headers['Host'], self.path))
            if self.path.startswith('/redirect'):
                host = 'next.example' if self.path == '/redirect-host' else 'calendar.example'
                self.send_response(302)
                self.send_header('Location', f'https://{host}:{self.server.server_port}/calendar.ics')
                # Following a redirect must not first download its unbounded body.
                self.send_header('Content-Length', '100000000')
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/calendar; charset=utf-8')
            self.send_header('Content-Length', str(len(ICS.encode())))
            self.end_headers()
            self.wfile.write(ICS.encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    context.set_servername_callback(lambda sock, name, ctx: seen['sni'].append(name))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    thread.start()
    real_resolve = socket.getaddrinfo
    real_connect = urllib3.util.connection.create_connection
    answers, unreachable = {}, set()

    def resolve(host, port, *args, **kwargs):
        if host.endswith('.example'):
            seen['dns'][host] += 1
            batches = answers.get(host, [[PUBLIC], ['127.0.0.1']])
            addresses = batches[min(seen['dns'][host] - 1, len(batches) - 1)]
            return [(socket.AF_INET6 if ':' in address else socket.AF_INET,
                     socket.SOCK_STREAM, 6, '',
                     (address, port, 0, 0) if ':' in address else (address, port))
                    for address in addresses]
        ipaddress.ip_address(host)  # An unexpected external hostname must not escape this test.
        return real_resolve(host, port, *args, **kwargs)

    def connect(address, *args, **kwargs):
        seen['connections'].append(address)
        host, port = address
        assert host in {PUBLIC, PUBLIC_V6}, 'the transport re-resolved an unchecked hostname'
        assert port == server.server_port
        if host in unreachable:
            raise OSError('Invented unreachable address')
        # Only the test transport maps these public addresses to its local server.
        return real_connect(('127.0.0.1', server.server_port), *args, **kwargs)

    monkeypatch.setattr(socket, 'getaddrinfo', resolve)
    monkeypatch.setattr(urllib3.util.connection, 'create_connection', connect)
    monkeypatch.setattr(requests.adapters, 'DEFAULT_CA_BUNDLE_PATH', str(cert))
    for name in ('http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
        monkeypatch.delenv(name, raising=False)
    try:
        yield f'https://calendar.example:{server.server_port}', seen, answers, unreachable
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize('mode', ['single', 'cloud'])
@pytest.mark.parametrize('address', [PUBLIC, PUBLIC_V6])
def test_rebinding_cannot_change_the_socket_destination_and_tls_keeps_the_hostname(
        transport, monkeypatch, mode, address):
    origin, seen, answers, _ = transport
    answers['calendar.example'] = [[address], ['127.0.0.1']]
    monkeypatch.setenv('DINKYDASH_MODE', mode)
    events = calendars.fetch_feed(origin + '/calendar.ics', date(2026, 9, 7),
                                  date(2026, 9, 21), calendars.zone('UTC'))
    assert [event['title'] for event in events] == ['Swimming']
    assert seen['dns']['calendar.example'] == 1
    assert [target[0] for target in seen['connections']] == [address]
    assert seen['sni'] == ['calendar.example']
    assert seen['requests'] == [(origin.removeprefix('https://'), '/calendar.ics')]


def test_a_same_host_redirect_rechecks_dns_before_another_connection(transport):
    origin, seen, _, _ = transport
    with pytest.raises(FeedRefused, match='private network'):
        calendars.fetch_text(origin + '/redirect')
    assert seen['dns']['calendar.example'] == 2
    assert len(seen['connections']) == 1


def test_a_public_redirect_uses_its_own_hostname_and_does_not_read_the_redirect_body(transport):
    origin, seen, _, _ = transport
    assert calendars.fetch_text(origin + '/redirect-host') == ICS
    assert seen['sni'] == ['calendar.example', 'next.example']
    assert seen['requests'][1][0] == origin.replace('https://calendar', 'next')


def test_environment_proxies_cannot_resolve_the_calendar_elsewhere(transport, monkeypatch):
    origin, seen, _, _ = transport
    monkeypatch.setenv('HTTPS_PROXY', 'http://proxy.example:8123')
    monkeypatch.setenv('ALL_PROXY', 'http://proxy.example:8123')
    monkeypatch.setenv('NO_PROXY', '')
    assert calendars.fetch_text(origin + '/calendar.ics') == ICS
    assert seen['dns']['proxy.example'] == 0


def test_a_failed_public_address_can_fall_back_to_another_validated_address(transport):
    origin, seen, answers, unreachable = transport
    answers['calendar.example'] = [[PUBLIC_V6, PUBLIC]]
    unreachable.add(PUBLIC_V6)
    assert calendars.fetch_text(origin + '/calendar.ics') == ICS
    assert [target[0] for target in seen['connections']] == [PUBLIC_V6, PUBLIC]
    assert seen['dns']['calendar.example'] == 1


def test_a_certificate_for_another_hostname_is_rejected(transport):
    origin, seen, _, _ = transport
    with pytest.raises(FeedError):
        calendars.fetch_text(origin.replace('calendar.example', 'wrong.example') + '/calendar.ics')
    assert seen['sni'] == ['wrong.example']
    assert seen['requests'] == []


def test_an_untrusted_certificate_is_rejected(transport, monkeypatch):
    origin, seen, _, _ = transport
    monkeypatch.setattr(requests.adapters, 'DEFAULT_CA_BUNDLE_PATH', requests.certs.where())
    with pytest.raises(FeedError):
        calendars.fetch_text(origin + '/calendar.ics')
    assert seen['sni'] == ['calendar.example']
    assert seen['requests'] == []
