# cypher

Universal **lossless file ↔ audio codec**.

`cypher` converts **any file type** into self-contained audio (`FLAC` / `WAV`) and restores the original file automatically.

Supported payloads:

- images
- PDFs
- videos
- source code
- archives
- binaries
- documents
- arbitrary MIME types

---

# Concept

Encode:

```txt
ANY FILE
↓
raw bytes
↓
embedded metadata
↓
compression
↓
optional encryption
↓
PCM16 payload
↓
FLAC / WAV
```

Decode:

```txt
FLAC / WAV
↓
PCM16 payload
↓
optional decryption
↓
decompression
↓
metadata recovery
↓
original file restoration
```

No external `.json` metadata file.

---

# Features

- universal file support
- any MIME type
- lossless encode / decode
- FLAC output
- WAV output
- embedded metadata
- automatic filename restoration
- SHA256 integrity verification
- optional asymmetric encryption
- inspect command
- tqdm progress bars
- self-contained containers

---

# Installation

Create environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install:

```bash
pip install -e .
```

---

# Project Structure

```txt
cypher/
├── .keys/
├── data/
│   ├── input/
│   ├── audio/
│   └── output/
├── src/
│   └── cypher/
│       ├── __init__.py
│       └── main.py
├── Makefile
├── pyproject.toml
└── README.md
```

---

# Usage

## Generate keys

Generate an encryption keypair:

```bash
make keygen
```

Keys are stored locally:

```txt
.keys/cypher_private.pem
.keys/cypher_public.pem
```

Use force overwrite:

```bash
make keygen-force
```

---

## Encode

Put files in:

```txt
data/input/
```

Encode:

```bash
make encode rapport.pdf
```

Default output:

```txt
data/audio/rapport.flac
```

WAV mode:

```bash
make encode rapport.pdf FORMAT=wav
```

### Automatic encryption

If:

```txt
.keys/cypher_public.pem
```

exists, encryption is automatically enabled.

---

## Decode

Decode:

```bash
make decode rapport.flac
```

Automatic restore:

```txt
data/output/rapport.pdf
```

Custom output:

```bash
make decode rapport.flac restored.pdf
```

### Automatic decryption

If:

```txt
.keys/cypher_private.pem
```

exists, decryption is automatically used.

If missing, cypher will request a private key path.

---

## Inspect

Inspect an audio payload without decoding:

```bash
make inspect rapport.flac
```

Displays:

```txt
original filename
mime type
encryption mode
payload size
checksum
compression backend
```

---

# Security

V4.5 supports optional **PGP-like encryption**.

Backend:

```txt
X25519
+
AES-GCM
+
HKDF-SHA256
```

Important:

```txt
KEEP THE PRIVATE KEY SECRET.
```

Never commit:

```txt
.keys/
*.pem
```

Public metadata remains inspectable without decryption:

- original filename
- mime type
- payload size
- checksum
- encryption mode

Payload content remains encrypted.

---

# Compression Pipeline

Current backend:

```txt
zlib
```

Pipeline:

```txt
raw bytes
→ metadata container
→ compression
→ optional encryption
→ PCM16 samples
→ FLAC / WAV
```

---

# Audio Formats

## FLAC

Recommended.

```txt
lossless
smaller
bit-perfect
```

## WAV

Supported.

```txt
lossless
larger files
maximum compatibility
```

## MP3

Rejected.

Reason:

```txt
MP3 is lossy.

Arbitrary binary payloads cannot be restored reliably.
```

---

# CLI

Direct usage:

Encode:

```bash
python -m cypher.main encode rapport.pdf
```

Decode:

```bash
python -m cypher.main decode rapport.flac
```

Inspect:

```bash
python -m cypher.main inspect rapport.flac
```

Generate keys:

```bash
python -m cypher.main keygen
```

Version:

```bash
python -m cypher.main --version
```

---

# Possible Improvements (V5+)

Potential future directions:

- Brotli backend
- LZMA backend
- adaptive compression selection
- chunked streaming mode
- multi-file bundles
- encrypted metadata mode
- digital signatures
- Reed-Solomon error correction
- steganographic transport
- distributed payload splitting
- robust lossy transport experiments
- optional password-protected private keys
- encrypted `.keys` storage
- payload deduplication
- audio watermarking

--

V4.6 → encrypted metadata mode
OK   (inspect ne révèle plus filename/mime)

V4.7 → bundle mode
OK      1 FLAC = plusieurs fichiers

V4.8 → chunked transport
      gros payloads / streaming

V5 → password-protected private keys
     + signatures
     + multi-recipient encryption