import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("quicksave_app", Path(__file__).resolve().parents[1] / "app.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_youtube_default_url_is_updated():
    youtube_link = next(item for item in module.DEFAULT_LINKS if item[0] == "YouTube")
    assert youtube_link[2] == "https://app.ytdown.to/en38/"


def test_locale_detection_supports_spanish():
    assert module.detect_locale("es-ES,es;q=0.9,en;q=0.8") == "es"
    assert module.detect_locale("fr-FR,fr;q=0.9") == "fr"


def test_postgres_detection_from_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/dbname")
    assert module.is_postgres_database() is True


def test_sqlite_is_default_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert module.is_postgres_database() is False


def test_db_uses_postgres_when_database_url_is_present(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/dbname")

    class DummyCursor:
        def execute(self, query, params=()):
            return query, params

        def executemany(self, query, params_seq):
            return query, params_seq

        def close(self):
            pass

    class DummyConnection:
        def __init__(self, dsn, **kwargs):
            self.dsn = dsn
            self.autocommit = False
            self.cursor_obj = DummyCursor()

        def cursor(self, **kwargs):
            return DummyCursor()

        def close(self):
            pass

        def commit(self):
            pass

        def rollback(self):
            pass

    monkeypatch.setattr(module.psycopg2, "connect", DummyConnection)
    db = module.db()
    assert isinstance(db, module.PostgresConnection)
    db.close()


def test_postgres_execute_keeps_fetch_available():
    class DummyCursor:
        def execute(self, query, params=()):
            self.query = query
            self.params = params

        def fetchone(self):
            return {"username": "admin"}

    connection = module.PostgresConnection.__new__(module.PostgresConnection)
    connection.cursor_obj = DummyCursor()

    row = connection.execute("SELECT username FROM admin_users WHERE username=?", ("admin",)).fetchone()

    assert row["username"] == "admin"
    assert connection.cursor_obj.query.endswith("username=%s")
    assert connection.cursor_obj.params == ("admin",)


def test_postgres_enabled_values_use_boolean(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/dbname")

    assert module.enabled_where_clause() == "enabled = TRUE"
    assert module.enabled_value(True) is True
    assert module.enabled_value(False) is False
