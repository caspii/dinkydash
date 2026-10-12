"""How the cloud connection pool is built.

`pool()` is what the web app and the worker share. A connection taken from it
has to be one the server can still answer on, and the settings that make that
true have to survive the arguments callers already pass — `min_size`,
`max_size`, and anything else the pool constructor takes.

The first two tests build an unopened pool, so they connect to nothing, and
libpq's own conninfo builder is what rejects a parameter it does not know, on
a TCP URL and on a hostless one. The checkout test uses the scratch database
when one is configured, and skips otherwise. psycopg is imported inside the
test, so a self-hoster's suite still collects without the cloud driver.
"""

import pytest


def _pool(*args, **kwargs):
    pytest.importorskip("psycopg_pool")
    from dinkydash import db

    kwargs.setdefault("open", False)
    return db.pool(*args, **kwargs)


class TestThePool:
    def test_a_connection_is_checked_and_the_socket_is_kept_alive(self):
        from psycopg.conninfo import conninfo_to_dict, make_conninfo
        from psycopg_pool import ConnectionPool

        from dinkydash import db

        pool = _pool("postgresql://localhost/unused")
        try:
            assert pool._check is ConnectionPool.check_connection
            assert pool._configure is db._prepare
            assert pool.kwargs == {
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 3,
                "connect_timeout": 10,
            }
            # The bounds the pool already had. Size is still the small one,
            # and lifetime and idle stay where psycopg put them.
            assert pool.min_size == 1
            assert pool.max_size == 3
            assert pool.timeout == 30
            assert pool.max_lifetime == 60 * 60
            assert pool.max_idle == 10 * 60
            assert pool._opened is False

            connection = type("Connection", (), {"prepare_threshold": 5})()
            pool._configure(connection)
            assert connection.prepare_threshold is None

            # libpq accepts the parameters. A hostless URL is a Unix socket
            # when nothing else names a host; the keepalive keys are still
            # legal there, and libpq ignores them at connect time.
            for conninfo in ("postgresql://localhost/unused", "postgresql:///unused"):
                parsed = conninfo_to_dict(make_conninfo(conninfo, **pool.kwargs))
                assert parsed["keepalives"] == "1"
                assert parsed["keepalives_idle"] == "30"
                assert parsed["keepalives_interval"] == "10"
                assert parsed["keepalives_count"] == "3"
                assert parsed["connect_timeout"] == "10"
        finally:
            pool.close()

    def test_caller_arguments_are_kept(self):
        """Callers pass a size, a timeout and connect options, and those arrive intact.

        The check and the keepalives stay in place beside them. A connect
        parameter the caller names wins over the one this module sets, because
        the caller is the one looking at that database.
        """
        from psycopg_pool import ConnectionPool

        from dinkydash import db

        pool = _pool(
            "postgresql://localhost/unused",
            min_size=1,
            max_size=2,
            timeout=15,
            max_lifetime=120,
            kwargs={"application_name": "dinkydash-test", "connect_timeout": 5},
        )
        try:
            assert pool._check is ConnectionPool.check_connection
            assert pool._configure is db._prepare
            assert pool.min_size == 1
            assert pool.max_size == 2
            assert pool.timeout == 15
            assert pool.max_lifetime == 120
            assert pool.max_idle == 10 * 60
            assert pool.kwargs == {
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 3,
                "connect_timeout": 5,
                "application_name": "dinkydash-test",
            }
        finally:
            pool.close()

    def test_checkout_leaves_an_idle_connection(self, pg_pool):
        """The probe runs on the way out of the pool and leaves the session idle.

        An open transaction would pin a server connection for as long as this
        client held the socket, which is what a transaction-mode pooler does
        with a session that has begun one. On TCP the kernel keepalive timers
        are the ones the pool asked for. A Unix socket has no such timers;
        libpq ignores them, and the connection still answers.
        """
        import socket

        from psycopg.pq import TransactionStatus

        with pg_pool.connection() as conn:
            assert conn.autocommit is False
            assert conn.info.transaction_status == TransactionStatus.IDLE
            assert conn.prepare_threshold is None
            if not str(conn.info.host).startswith("/"):
                raw = socket.fromfd(conn.fileno(), socket.AF_INET, socket.SOCK_STREAM)
                try:
                    assert raw.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) == 1
                    assert raw.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE) == 30
                    assert raw.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL) == 10
                    assert raw.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT) == 3
                finally:
                    raw.close()
            assert conn.execute("SELECT 1").fetchone() == (1,)
