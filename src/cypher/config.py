"""
Global configuration for cypher.
"""

from pathlib import Path


PROJECT_NAME = "cypher"
VERSION = "0.1.0"

# -------------------------------------------------------------------
# Audio configuration
# -------------------------------------------------------------------

DEFAULT_SAMPLE_RATE = 44_100

DEFAULT_PIXEL_DURATION = 0.01

DEFAULT_AMPLITUDE = 0.3

PCM_BIT_DEPTH = 16

# -------------------------------------------------------------------
# RGB frequency mapping
# -------------------------------------------------------------------

R_MIN_FREQ = 300.0
R_MAX_FREQ = 1000.0

G_MIN_FREQ = 1200.0
G_MAX_FREQ = 1900.0

B_MIN_FREQ = 2100.0
B_MAX_FREQ = 2800.0

# -------------------------------------------------------------------
# Header configuration
# -------------------------------------------------------------------

MAGIC = "CYPHER"

HEADER_VERSION = 1

COLOR_MODE = "RGB"

PIXEL_MODE = "RGB_3_FREQ"

CHECKSUM_ALGORITHM = "SHA256"

# -------------------------------------------------------------------
# FSK header encoding
# -------------------------------------------------------------------

FSK_ZERO_FREQ = 1200.0

FSK_ONE_FREQ = 2200.0

FSK_BIT_DURATION = 0.01

# -------------------------------------------------------------------
# Supported formats
# -------------------------------------------------------------------

SUPPORTED_INPUT_IMAGES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
}

SUPPORTED_AUDIO_OUTPUT = {
    ".wav",
}

# -------------------------------------------------------------------
# Default paths
# -------------------------------------------------------------------

DATA_DIR = Path("data")

INPUT_DIR = DATA_DIR / "input"

AUDIO_DIR = DATA_DIR / "audio"

OUTPUT_DIR = DATA_DIR / "output"

# -------------------------------------------------------------------
# FFT / decoder settings
# -------------------------------------------------------------------

FFT_WINDOW = "hann"

NOISE_THRESHOLD = 1e-6

# -------------------------------------------------------------------
# Debug
# -------------------------------------------------------------------

DEBUG = False
