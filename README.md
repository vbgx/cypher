# cypher

Universal **lossless file ↔ audio codec**.

`cypher` converts **any file type** into self-contained **FLAC / WAV encrypted audio containers** and restores the original payload automatically.

Supported payloads:

- images
- PDFs
- videos
- source code
- archives
- binaries
- documents
- arbitrary MIME types
- multi-file bundles

---

# Concept

Single file mode:

```
ANY FILE
↓
raw bytes
↓
container
↓
chunked transport
↓
compression
↓
encryption
↓
PCM16 payload
↓
FLAC / WAV
```

Bundle mode:

```
MULTIPLE FILES
↓
bundle container
↓
chunked transport
↓
compression
↓
encryption
↓
FLAC / WAV
```

Decode:

```
FLAC / WAV
↓
PCM16 payload
↓
chunk reconstruction
↓
Touch ID authentication
↓
decryption
↓
decompression
↓
container recovery
↓
original payload restoration
```

No external metadata files.

---

# Features

- universal file support
- arbitrary MIME types
- lossless encode / decode
- FLAC support
- WAV support
- embedded containers
- automatic filename restoration
- SHA256 integrity verification
- asymmetric encryption
- encrypted metadata mode
- chunked transport
- bundle mode
- inspect mode
- Touch ID protected private key access
- self-contained containers

---

# Installation

Create environment:

```
python-m venv .venv
source .venv/bin/activate
```

Install:

```
pip install-e .
```

---

# Project Structure

```
cypher/
├── .keys/
│   ├── cypher_private.pem
│   └── cypher_public.pem
│
├── data/
│   ├── input/
│   ├── audio/
│   │   └── bundle/
│   └── output/
│
├── src/
│   └── cypher/
│       ├── __init__.py
│       └── main.py
│
├── Makefile
├── pyproject.toml
└── README.md
```

---

# Usage

## Generate Keys

Generate encryption keys:

```
make keygen
```

Output:

```
.keys/cypher_private.pem
.keys/cypher_public.pem
```

Force overwrite:

```
make keygen-force
```

Private key behavior:

```
private PEM encrypted at rest
password stored in macOS Keychain
```

---

## Encode — Single File

Place files inside:

```
data/input/
```

Encode:

```
make encode rapport.pdf
```

Output:

```
data/audio/<random>.flac
```

WAV:

```
make encode rapport.pdfFORMAT=wav
```

Automatic encryption activates when:

```
.keys/cypher_public.pem
```

exists.

---

## Decode — Single File

Decode:

```
make decode file.flac
```

Output:

```
data/output/original_file.ext
```

Custom output:

```
make decode file.flac restored.ext
```

Authentication flow:

```
Touch ID popup
↓
private key unlock
↓
payload decrypt
↓
restore file
```

---

## Bundle — Multiple Files

Create one encrypted container from multiple files:

```
make bundle rapport.pdf video.mp4 py.py image.jpg
```

Output:

```
data/audio/bundle/<random>.flac
```

---

## Unbundle

Restore bundled payloads:

```
make unbundle file.flac
```

Output:

```
data/output/bundle/
```

Example:

```
data/output/bundle/
├── rapport.pdf
├── video.mp4
├── py.py
└── image.jpg
```

Touch ID authentication is required before decryption.

---

## Inspect

Inspect a container without decoding:

```
make inspect file.flac
```

Shows:

```
cypher version
payload mode
encryption mode
stored payload size
```

Encrypted payloads hide:

```
filename
mime type
checksum
embedded metadata
```

---

# Security

Encryption backend:

```
X25519
+
AES-GCM
+
HKDF-SHA256
```

Private key protection:

```
PEM encrypted at rest
+
macOS Keychain
+
Touch ID unlock
```

Recommended:

```
never commit .keys/
never commit *.pem
```

---

# Transport Architecture

## Compression

Current backend:

```
zlib
```

## Chunked Transport — V4.8

Large payloads are processed chunk-by-chunk.

Pipeline:

```
container
↓
split chunks
↓
compress
↓
encrypt
↓
serialize
↓
audio transport
```

Advantages:

- large payload handling
- reduced RAM pressure
- scalable transport
- streaming-style reconstruction

---

# Audio Formats

## FLAC

Recommended.

```
lossless
smaller
bit-perfect
```

## WAV

Supported.

```
lossless
larger
maximum compatibility
```

## MP3

Rejected.

Reason:

```
lossy codec
not bit-perfect
unsafe for arbitrary binary recovery
```

---

# CLI

Encode:

```
python-m cypher.main encode rapport.pdf
```

Decode:

```
python-m cypher.main decode file.flac
```

Bundle:

```
python-m cypher.main bundle file1 file2 file3
```

Unbundle:

```
python-m cypher.main unbundle bundle.flac
```

Inspect:

```
python-m cypher.main inspect file.flac
```

Keys:

```
python-m cypher.main keygen
```

Version:

```
python-m cypher.main--version
```

---

# Implemented Versions

## V4.6 — Encrypted Metadata Mode

✓ implemented

`inspect` no longer reveals:

- filename
- MIME type
- checksum
- metadata

for encrypted payloads.

---

## V4.7 — Bundle Mode

✓ implemented

```
1 FLAC
=
multiple files
```

Supported workflows:

```
make bundle
make unbundle
```

---

## V4.8 — Chunked Transport

✓ implemented

Large payload handling:

- chunk splitting
- per-chunk compression
- per-chunk encryption
- scalable reconstruction

---

## V4.9 — Keychain + Touch ID

✓ implemented

Private key protection:

```
encrypted private PEM
+
macOS Keychain secret storage
+
Touch ID authentication
```

`decode` and `unbundle` require biometric validation before decryption.

---

# Possible Improvements (V5+)

Potential future directions:

- digital signatures
- multi-recipient encryption
- Brotli backend
- LZMA backend
- adaptive compression selection
- Reed-Solomon error correction
- steganographic transport
- distributed payload splitting
- payload deduplication
- encrypted `.keys` storage
- audio watermarking
- experimental lossy-resilient transport
- remote / streamed decoding
- progressive partial recovery