# cypher

Universal **lossless file ↔ audio codec**.

`cypher` converts **any file type** into self-contained audio (`FLAC` / `WAV`) and reconstructs the original file automatically.

Supported payloads include:

- images
- PDFs
- videos
- archives
- source code
- binaries
- audio
- documents
- arbitrary MIME types

---

# Concept

Traditional storage:

```txt
file
→ binary file
```

cypher V4.3:

```
ANY FILE
↓
raw bytes
↓
embedded metadata header
↓
container
↓
lossless compression
↓
PCM16 audio payload
↓
FLAC / WAV
```

Decode:

```
FLAC / WAV
↓
PCM16 payload
↓
decompression
↓
container parsing
↓
embedded metadata recovery
↓
original file restoration
```

The decoder automatically restores:

```
filename
extension
mime type
payload
checksum
```

No external metadata file required.

---

# Features

- universal file support
- any MIME type
- lossless encode
- lossless decode
- FLAC output
- WAV output
- embedded metadata
- automatic filename recovery
- SHA256 integrity verification
- tqdm progress bars
- self-contained audio containers

---

# Installation

Clone:

```
git clone <repo>
cd cypher
```

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
├── README.md
├── Makefile
├── pyproject.toml
├── data/
│   ├── input/
│   ├── audio/
│   └── output/
└── src/
    └── cypher/
        ├── __init__.py
        └── main.py
```

---

# Usage

## Encode

Place files inside:

```
data/input/
```

Examples:

```
data/input/report.pdf
data/input/video.mp4
data/input/script.py
data/input/archive.zip
data/input/image.jpg
```

Encode:

```
make encode report.pdf
```

or:

```
make encode video.mp4
```

or:

```
make encode script.py
```

Default output:

```
FLAC
```

Produces:

```
data/audio/report.flac
```

---

## WAV output

Use WAV:

```
make encode report.pdfFORMAT=wav
```

Produces:

```
data/audio/report.wav
```

---

# Decode

Decode requires **only the audio file**.

Automatic restore:

```
make decode report.flac
```

Produces:

```
data/output/report.pdf
```

You can still override output name:

```
make decode report.flac report_restored.pdf
```

Examples:

```
make decode video.flac
make decode script.flac
make decode archive.flac
```

Automatic outputs:

```
data/output/video.mp4
data/output/script.py
data/output/archive.zip
```

---

# Examples

## PDF

Encode:

```
make encode rapport.pdf
```

Decode:

```
make decode rapport.flac
```

---

## MP4 Video

Encode:

```
make encode video.mp4
```

Decode:

```
make decode video.flac
```

---

## Python Source

Encode:

```
make encode py.py
```

Decode:

```
make decode py.flac
```

---

## ZIP Archive

Encode:

```
make encode archive.zip
```

Decode:

```
make decode archive.flac
```

---

# Embedded Metadata

V4.3 stores metadata **inside the audio container**.

Embedded fields:

- original filename
- original extension
- MIME type
- checksum
- payload size
- codec version
- compression algorithm

No `.json` sidecar file is generated.

---

# Integrity Verification

cypher uses SHA256 validation.

Encode:

```
checksum generated
```

Decode:

```
checksum verified
```

Failure:

```
checksum mismatch
→ decode aborted
```

---

# Compression Pipeline

Current backend:

```
zlib
```

Pipeline:

```
raw bytes
→ metadata header
→ container
→ zlib compression
→ PCM16 samples
→ FLAC/WAV
```

---

# Audio Formats

## FLAC

Recommended.

Properties:

- lossless
- smaller
- compact
- bit-perfect recovery

---

## WAV

Supported.

Properties:

- lossless
- larger files
- compatibility mode

---

## MP3

Rejected.

Reason:

```
MP3 is lossy.

Arbitrary file bytes cannot be restored reliably.
```

---

# Progress Monitoring

Large payloads show live progress.

Example:

```
Compressing embedded container...
Container size    : 11,930,126 bytes

Packing samples:
████████████████████ 100%

Writing audio:
data/audio/video.flac
```

Decode:

```
Reading audio...
Unpacking samples:
████████████████████ 100%

Decompressing embedded container...
Decode completed.
```

---

# CLI

Direct usage:

Encode:

```
python-m cypher.main encode report.pdf
```

Decode:

```
python-m cypher.main decode report.flac
```

Version:

```
python-m cypher.main--version
```

---

# Roadmap

## V1

RGB → frequency mapping.

```
image
→ frequencies
→ FFT decode
```

---

## V2

Amplitude-based RGB encoding.

---

## V3

Lossless RGB payload transport.

---

## V4.1

Universal file codec.

```
ANY FILE
→ bytes
→ audio
→ restored file
```

---

## V4.2

Embedded metadata containers.

No external JSON dependency.

---

## V4.3 (current)

Single-program architecture.

```
src/cypher/
├── __init__.py
└── main.py
```

Self-contained codec engine.

---

## Future Ideas

Potential V5:

- Brotli backend
- LZMA backend
- chunked streaming
- payload encryption
- Reed-Solomon error correction
- steganographic transport
- multi-file bundles
- experimental robust MP3 mode

---

# License

MIT
