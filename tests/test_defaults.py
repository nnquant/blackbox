from __future__ import annotations

from pathlib import Path


def test_default_data_paths_use_home(monkeypatch) -> None:
    monkeypatch.delenv("BLACKBOX_DATA_DIR", raising=False)
    monkeypatch.delenv("BLACKBOX_DATABASE_URL", raising=False)
    monkeypatch.delenv("BLACKBOX_ARTIFACT_ROOT", raising=False)
    monkeypatch.delenv("BLACKBOX_SPOOL_DIR", raising=False)

    from blackbox.offline import OfflineSpool
    from blackbox_server.settings import get_settings

    expected_root = Path("~/.blackbox").expanduser().resolve()
    settings = get_settings()
    assert settings.data_root == expected_root
    assert settings.database_url == f"sqlite:///{expected_root / 'blackbox.db'}"
    assert settings.artifact_root == expected_root / "artifacts"
    assert settings.artifact_storage == "local"
    assert settings.max_metric_payload_bytes == 65536

    spool = OfflineSpool()
    assert spool.root == expected_root
    assert spool.queue_dir == expected_root / "queue"
    assert spool.artifact_dir == expected_root / "artifacts"
    assert spool.manifests_dir == expected_root / "manifests"
