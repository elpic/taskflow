import pytest
import src.db as db_module


@pytest.fixture(autouse=True)
def patch_db_path(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp file and reset the _initialized flag for each test."""
    test_db = tmp_path / "test_taskflow.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    monkeypatch.setattr(db_module, "_initialized", False)
    yield
    # Ensure flag is reset even if a test raised
    db_module._initialized = False
