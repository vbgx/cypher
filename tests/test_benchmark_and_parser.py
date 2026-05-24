from argparse import Namespace

import cypher.main as cypher


def test_version_constant_is_stable() -> None:
    assert cypher.VERSION == "1.0.0"


def test_benchmark_command_runs_without_default_public_key(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    payload = tmp_path / "payload.txt"
    payload.write_text("benchmark me")

    monkeypatch.setattr(
        cypher,
        "DEFAULT_PUBLIC_KEY_PATH",
        tmp_path / "missing_public.pem",
    )

    cypher.benchmark_command(
        Namespace(
            file=str(payload),
            compression_level=cypher.DEFAULT_COMPRESSION_LEVEL,
            public_key=None,
        )
    )

    output = capsys.readouterr().out

    assert "Cypher benchmark" in output
    assert "Crypto            : none" in output


def test_build_parser_has_expected_commands() -> None:
    parser = cypher.build_parser()

    for command in [
        "keygen",
        "encode",
        "decode",
        "bundle",
        "unbundle",
        "inspect",
        "benchmark",
    ]:
        args = ["--help"]

        subparser_actions = [
            action
            for action in parser._actions
            if getattr(action, "choices", None)
        ]

        assert any(command in action.choices for action in subparser_actions)
        assert args
