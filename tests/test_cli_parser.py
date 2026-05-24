import cypher.main as cypher


def test_encode_accepts_multiple_public_keys():
    parser = cypher.build_parser()

    args = parser.parse_args(
        [
            "encode",
            "secret.pdf",
            "--public-key",
            "alice.pem",
            "--public-key",
            "bob.pem",
        ]
    )

    assert args.public_key == ["alice.pem", "bob.pem"]


def test_bundle_accepts_multiple_public_keys():
    parser = cypher.build_parser()

    args = parser.parse_args(
        [
            "bundle",
            "src",
            "--public-key",
            "alice.pem",
            "--public-key",
            "bob.pem",
        ]
    )

    assert args.public_key == ["alice.pem", "bob.pem"]
