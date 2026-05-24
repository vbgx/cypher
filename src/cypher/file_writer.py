from pathlib import Path


def write_file_bytes(
    path: str | Path,
    payload: bytes,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(payload)
