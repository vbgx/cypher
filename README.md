# cypher

Encode images into sound.  
Decode sound back into images.

`cypher` transforms an image into an audio representation and reconstructs the original image from that audio stream.

```txt
IMAGE → AUDIO → IMAGE
```

The project is based on deterministic pixel serialization and RGB frequency mapping.

---

# Concept

An image is read pixel by pixel.

Traversal order:

```txt
line 1:
(1,1) → (2,1) → ... → (width,1)

line 2:
(1,2) → (2,2) → ... → (width,2)

...

line N:
(1,height) → ... → (width,height)
```

Each pixel is converted into sound.

The decoder performs the reverse operation.

---

# Encoding model

Each RGB pixel:

```txt
R: 0–255
G: 0–255
B: 0–255
```

is represented by **three simultaneous frequencies**.

Example mapping:

```txt
R → low frequency band
G → medium frequency band
B → high frequency band
```

Default ranges:

```txt
R: 300 Hz → 1000 Hz
G: 1200 Hz → 1900 Hz
B: 2100 Hz → 2800 Hz
```

Mapping formula:

```txt
freq_R = 300  + R × 700 / 255
freq_G = 1200 + G × 700 / 255
freq_B = 2100 + B × 700 / 255
```

Each pixel becomes a short audio frame.

---

# Resolution independence

Images may have **any resolution**.

Dimensions are stored inside an audio header.

The decoder does not need prior knowledge of image size.

Supported examples:

```txt
32×32
100×100
1920×1080
4096×4096
...
```

---

# Audio format

Generated audio uses:

```txt
WAV
PCM
```

Structure:

```txt
HEADER
+
PIXEL STREAM
```

---

# Header

The audio stream begins with metadata.

Example:

```txt
MAGIC       = CYPHER
VERSION     = 1
WIDTH       = 100
HEIGHT      = 100
COLOR_MODE  = RGB
PIXEL_MODE  = RGB_3_FREQ
PIXEL_TIME  = 0.01
CHECKSUM    = SHA256
```

Serialized example:

```txt
CYPHER|1|100|100|RGB|RGB_3_FREQ|0.01|sha256...
```

Header encoding may use binary FSK.

Example:

```txt
0 → 1200 Hz
1 → 2200 Hz
```

---

# Encode workflow

```txt
image
↓
read pixels
↓
serialize metadata
↓
map RGB → frequencies
↓
generate audio frames
↓
write WAV
```

---

# Decode workflow

```txt
WAV
↓
read header
↓
recover width / height
↓
split audio into frames
↓
extract frequencies
↓
recover RGB values
↓
rebuild image
```

---

# Installation

Clone repository:

```bash
git clone https://github.com/yourname/cypher.git
cd cypher
```

Create environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -e .
```

---

# Usage

Encode image → audio:

```bash
cypher encode input.png output.wav
```

Decode audio → image:

```bash
cypher decode output.wav restored.png
```

Custom pixel duration:

```bash
cypher encode input.png output.wav \
    --pixel-duration 0.01
```

---

# Example

Input:

```txt
100 × 100 image
```

Pixel count:

```txt
10 000 pixels
```

If:

```txt
1 pixel = 10 ms
```

Then:

```txt
10 000 × 10 ms
=
100 seconds audio
```

---

# Repository structure

```txt
cypher/
├── README.md
├── pyproject.toml
├── data/
│   ├── input/
│   ├── audio/
│   └── output/
├── src/
│   └── cypher/
│       ├── __init__.py
│       ├── cli.py
│       ├── image_reader.py
│       ├── image_writer.py
│       ├── audio_encoder.py
│       ├── audio_decoder.py
│       ├── header.py
│       ├── mapping.py
│       ├── checksum.py
│       └── config.py
└── tests/
    ├── test_mapping.py
    ├── test_header.py
    └── test_roundtrip.py
```

---

# Roadmap

## V1

- PNG / JPG input
- WAV output
- RGB support
- audio header
- deterministic pixel traversal
- RGB → frequency mapping
- decode support
- checksum validation

## V2

- lossless encoding improvements
- compression
- adaptive frequency allocation
- alpha channel support
- grayscale mode
- stereo encoding
- streaming mode

## V3

- real-time encoding
- spectrogram visualization
- live image/audio conversion
- experimental cryptographic modes

---

# Goals

`cypher` explores:

- image serialization
- signal encoding
- audio representation of visual data
- reversible media transformation
- deterministic multimedia encoding

---

# License

MIT