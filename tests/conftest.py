import pytest
import src.db as db_module


@pytest.fixture(autouse=True)
async def patch_db_path(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp file and reset the singleton for each test."""
    test_db = tmp_path / "test_taskflow.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    monkeypatch.setattr(db_module, "_db", None)
    yield
    await db_module.close_db()
