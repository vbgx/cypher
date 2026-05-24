from pathlib import Path


def resolve_input_file(path: str | Path, input_dir: Path) -> Path:
    candidate = Path(path)

    if candidate.exists():
        return candidate

    candidate = input_dir / path

    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Input file not found: {path}")


def read_file_bytes(path: str | Path) -> bytes:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    return file_path.read_bytes()
