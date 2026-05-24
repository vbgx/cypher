
import pytest

import cypher.main as cypher


@pytest.fixture()
def isolated_runtime(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.setattr(cypher, "DATA_DIR", data_dir)

    return tmp_path
