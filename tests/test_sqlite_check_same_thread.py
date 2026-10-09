"""The file SQLite engine can serve a FastAPI worker thread."""

import threading

from app.core.database import create_db_engine


def test_sqlite_file_connection_works_on_another_thread(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    connection = engine.connect()
    errors = []

    def read():
        try:
            connection.exec_driver_sql("SELECT 1").scalar()
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=read)
    worker.start()
    worker.join()
    connection.close()
    engine.dispose()
    assert errors == []
