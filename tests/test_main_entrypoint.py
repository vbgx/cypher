from argparse import Namespace

import cypher.main as cypher


class FakeParser:
    def __init__(self):
        self.args = Namespace(func=lambda args: setattr(args, "called", True))

    def parse_args(self):
        return self.args


def test_main_dispatches_to_selected_command(monkeypatch) -> None:
    parser = FakeParser()

    monkeypatch.setattr(
        cypher,
        "build_parser",
        lambda: parser,
    )

    cypher.main()

    assert parser.args.called is True


def test_keygen_command_passes_args(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(
        cypher,
        "generate_keypair",
        lambda private_key_path, public_key_path, force: calls.append(
            (private_key_path, public_key_path, force)
        ),
    )

    cypher.keygen_command(
        Namespace(
            private_key="private.pem",
            public_key="public.pem",
            force=True,
        )
    )

    private_key_path, public_key_path, force = calls[0]

    assert str(private_key_path) == "private.pem"
    assert str(public_key_path) == "public.pem"
    assert force is True
