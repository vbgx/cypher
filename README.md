# cypher

Universal **lossless file ↔ audio codec**.

`cypher` converts arbitrary files, bundles, and complete folders into self-contained encrypted **FLAC / WAV containers** and restores them losslessly.

---

# Features

- universal file support
- arbitrary MIME types
- lossless encode / decode
- FLAC support
- WAV support
- chunked transport
- bundle mode
- complete folder support
- relative path preservation
- encrypted metadata mode
- SHA256 integrity verification
- X25519 + AES-GCM encryption
- Touch ID protected private key access
- GUI interface
- drag & drop
- inspect mode

---

# Concept

Single file:

```txt
FILE
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

Bundle / folder:

```txt
FILES / DIRECTORY
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

```txt
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
payload restoration
```

No external metadata files.

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
│       ├── main.py
│       └── gui.py
│
├── Makefile
├── pyproject.toml
└── README.md
```

---

# Key Generation

Generate encryption keys:

```bash
make keygen
```

Force overwrite:

```bash
make keygen-force
```

Generated files:

```txt
.keys/cypher_private.pem
.keys/cypher_public.pem
```

Security model:

```txt
private PEM encrypted at rest
+
password stored in macOS Keychain
+
Touch ID unlock
```

---

# Encode — Single File

Place payload inside:

```txt
data/input/
```

Encode:

```bash
make encode rapport.pdf
```

Output:

```txt
data/audio/<random>.flac
```

WAV mode:

```bash
make encode rapport.pdf FORMAT=wav
```

Encryption automatically activates when:

```txt
.keys/cypher_public.pem
```

exists.

---

# Bundle — Multiple Files / Folders

Multiple files:

```bash
make bundle rapport.pdf video.mp4 py.py
```

Folder:

```bash
make bundle data/input/projet_prout
```

Output:

```txt
data/audio/bundle/<random>.flac
```

Directory trees are preserved automatically.

---

# Decode — Universal Restore

`decode` handles:

- single files
- bundles
- complete folders

Decode:

```bash
make decode file.flac
```

Single file output:

```txt
data/output/original.ext
```

Bundle / folder output:

```txt
data/output/project_name/
```

Example:

```txt
data/output/projet_prout/
├── image.jpg
├── music.mp3
├── py.py
├── rapport.pdf
└── video.mp4
```

Touch ID authentication occurs before decryption.

Custom restore target:

```bash
make decode file.flac custom_output
```

---

# Inspect

Inspect a container without restoring it:

```bash
make inspect file.flac
```

Displays:

```txt
cypher version
payload mode
encryption mode
stored payload size
chunk information
```

Encrypted metadata mode hides:

```txt
filename
mime type
checksum
embedded metadata
```

---

# GUI

Launch graphical interface:

```bash
make gui
```

Current GUI capabilities:

- file selector
- folder selector
- drag & drop
- encode
- bundle
- decode
- inspect
- console logs
- automatic single/bundle detection
- recursive folder handling
- directory reconstruction

---

# Security

Encryption backend:

```txt
X25519
+
AES-GCM
+
HKDF-SHA256
```

Private key protection:

```txt
encrypted private PEM
+
macOS Keychain
+
Touch ID authentication
```

Recommended:

```txt
never commit .keys/
never commit *.pem
```

---

# Transport Architecture

Compression backend:

```txt
zlib
```

Chunked transport pipeline:

```txt
container
↓
chunk split
↓
compression
↓
encryption
↓
serialization
↓
audio transport
```

Advantages:

- large payload handling
- lower memory pressure
- scalable transport
- streaming-style reconstruction

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
larger
maximum compatibility
```

## MP3

Unsupported.

Reason:

```txt
lossy codec
not bit-perfect
unsafe for binary restoration
```

---

# CLI

Encode:

```bash
python -m cypher.main encode rapport.pdf
```

Bundle:

```bash
python -m cypher.main bundle file1 file2 folder/
```

Decode:

```bash
python -m cypher.main decode file.flac
```

Inspect:

```bash
python -m cypher.main inspect file.flac
```

Keys:

```bash
python -m cypher.main keygen
```

Version:

```bash
python -m cypher.main --version
```

---

# Implemented Versions

## V4.6 — Encrypted Metadata Mode

✓ implemented

`inspect` no longer reveals payload metadata for encrypted containers.

---

## V4.7 — Bundle Mode

✓ implemented

```txt
1 FLAC
=
multiple files
```

---

## V4.8 — Chunked Transport

✓ implemented

- chunk splitting
- per-chunk compression
- per-chunk encryption
- scalable reconstruction

---

## V4.9 — Keychain + Touch ID

✓ implemented

- encrypted private PEM
- macOS Keychain storage
- Touch ID authentication

---

## V5.0 — Minimal GUI

✓ implemented

- file selector
- folder selector
- encode
- bundle
- decode
- inspect
- live logs

---

## V5.1 — GUI + Folder Bundles

✓ implemented

- drag & drop
- auto single/bundle detection
- recursive folders
- relative path preservation
- directory reconstruction
- unified decode workflow

---

## V5.2 → live progress + ETA + improved GUI workflows
- real-time GUI progress tracking
- progress protocol between CLI and GUI
- phase-aware progress reporting
- weighted multi-phase progression
- live percentage updates
- chunk / audio / scan progress parsing
- dynamic ETA refinement during execution
- indeterminate preparation state
- command cancellation support
- improved long-running bundle UX
- better handling of large repositories / folders
- integrated GUI progress visualization

GUI improvements:

- encode starts immediately
- preparation phase shown explicitly
- automatic transition to real progress mode
- live phase display
- live ETA display
- better responsiveness for large datasets
- improved subprocess log streaming

---

---

# V5.3 — Stylish GUI

V5.3 introduces a redesigned graphical interface focused on usability, atmosphere, and real-time operational feedback.

The GUI now supports two dedicated visual environments:

## Obsidian Purple

A clean cyber-terminal interface optimized for readability.

Features:

- dark purple operator theme
- structured logs
- dashboard telemetry
- progress tracking
- ETA estimation
- artifact tracking
- operational audio feedback (`unlimited_power.mp3`)

Designed for:

```txt
clear monitoring
clean workflow visibility
long encoding / decoding sessions
```

## Matrix

A fully stylized encrypted console mode.

Features:

- green cryptographic interface
- Matrix-inspired visual theme
- obfuscated log stream rendering
- encrypted symbol output simulation
- real-time progress telemetry
- audio atmosphere (`matrix.mp3`)

The Matrix mode intentionally transforms log rendering into a visual signal stream:

```txt
01▓▒░█◆▣<>[]{}#%&@01▒▓█◇◆
```

while preserving the underlying command execution.

## GUI Features

V5.3 GUI currently includes:

- file selection
- folder selection
- automatic encode / bundle workflow
- automatic decode / restore workflow
- integrated inspect workflow
- dashboard metrics
    - items count
    - payload size
    - operation mode
    - crypto status
- real progress monitoring
- weighted ETA estimation
- operation cancellation
- output artifact tracking
- output folder quick access
- theme switching

The GUI is launched with:

```bash
make gui
```

or:

```bash
python -m cypher.gui
```

---

# Future Directions

Potential next steps:

- digital signatures
- multi-recipient encryption
- Brotli backend
- LZMA backend
- adaptive compression selection
- Reed-Solomon error correction
- distributed payload splitting
- payload deduplication
- encrypted `.keys` storage
- audio watermarking
- steganographic transport
- experimental lossy-resilient transport
- progressive partial recovery