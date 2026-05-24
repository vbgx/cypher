# cypher

**Universal file ↔ audio lossless codec**

`cypher` converts **any file type** into audio (`FLAC` / `WAV`) and reconstructs the original file **bit-perfect**.

Supported payloads include:

- images
- PDFs
- videos
- archives
- source code
- binaries
- documents
- audio
- essentially **any MIME type**

---

# Concept

Traditional storage:

```txt
file
→ binary file
```

cypher V4:

```
ANY FILE
↓
raw bytes
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
original bytes
↓
original file
```

Result:

```
INPUT FILE == OUTPUT FILE
```

verified by checksum.

---

# Features

- universal file support
- any MIME type
- lossless encoding
- lossless decoding
- FLAC output
- WAV output
- checksum verification
- metadata sidecar
- automatic original filename recovery
- tqdm progress monitoring
- deterministic roundtrip restoration

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
├── src/
│   └── cypher/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── header.py
│       ├── checksum.py
│       ├── audio_encoder.py
│       ├── audio_decoder.py
│       ├── file_reader.py
│       └── file_writer.py
└── tests/
```

---

# Usage

## Encode

Place any file inside:

```
data/input/
```

Examples:

```
data/input/report.pdf
data/input/video.mp4
data/input/py.py
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
make encode py.py
```

Default:

```
output format = FLAC
```

Produces:

```
data/audio/report.flac
data/audio/report.json
```

---

## WAV output

Use WAV instead of FLAC:

```
make encode report.pdfFORMAT=wav
```

Produces:

```
data/audio/report.wav
```

---

## Decode

Decode from audio:

```
make decode report.flac
```

or specify output filename:

```
make decode report.flac report_restored.pdf
```

Examples:

```
make decode video.flac video_decoded.mp4
make decode py.flac py_decoded.py
make decode archive.flac archive_restored.zip
```

Produces:

```
data/output/
```

---

# Important Decode Rule

Decode always takes the **audio file** as input.

Correct:

```
make encode py.py
make decode py.flac py_decoded.py
```

Incorrect:

```
make decode py.py py_decoded.py
```

because `decode` expects:

```
.flac
or
.wav
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
make decode rapport.flac rapport_restored.pdf
```

---

## MP4 Video

Encode:

```
make encode video.mp4
```

Decode:

```
make decode video.flac video_decoded.mp4
```

---

## Python Source Code

Encode:

```
make encode py.py
```

Decode:

```
make decode py.flac py_decoded.py
```

---

## ZIP Archive

Encode:

```
make encode archive.zip
```

Decode:

```
make decode archive.flac archive_restored.zip
```

---

# Metadata

Each encoded payload generates metadata.

Example:

```
data/audio/video.flac
data/audio/video.json
```

Metadata stores:

- original filename
- extension
- MIME type
- sample rate
- payload size
- compressed size
- checksum
- codec version
- compression algorithm

---

# Integrity Verification

cypher uses SHA256 verification.

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

# Compression

Current backend:

```
zlib
```

Pipeline:

```
raw bytes
→ zlib compression
→ PCM16 audio samples
→ FLAC / WAV
```

---

# Progress Monitoring

Large payloads show live progress.

Example:

```
Compressing payload...
Raw size          : 11,930,126 bytes

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

Decompressing payload...
Audio decode completed.
```

---

# Audio Formats

## FLAC

Recommended.

Properties:

- lossless
- compact
- smaller output
- bit-perfect recovery

## WAV

Supported.

Properties:

- lossless
- larger files
- debugging / compatibility

## MP3

Not supported for lossless restoration.

Reason:

```
MP3 is lossy.
Arbitrary file bytes cannot be reconstructed reliably.
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

Large files.

---

## V2

Fixed-frequency RGB amplitude encoding.

Improved but still audio-heavy.

---

## V3

Lossless RGB payload transport.

```
RGB bytes
→ compression
→ audio payload
```

---

## V4 (current)

Universal file codec.

```
ANY FILE
→ bytes
→ compression
→ audio
→ original file
```

---

## Future Ideas

Potential V5:

- Brotli backend
- LZMA backend
- chunked streaming
- encrypted payload mode
- Reed-Solomon error correction
- steganographic transport mode
- embedded metadata inside audio
- multi-file payload bundles
- experimental MP3 robust mode

---
