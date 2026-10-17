# sandbox-runner

Python code execution sandbox with multiple input methods. Accepts code as plain text, extracts it from images via OCR, from PDF documents, or from audio recordings via speech-to-text. All code runs inside a RestrictedPython sandbox with a configurable builtin allowlist.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

For the image OCR endpoint, [Tesseract](https://github.com/tesseract-ocr/tesseract) must be installed on the system:

```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt install tesseract-ocr
```

## Usage

Start the server:

```bash
python server.py
```

The server listens on port 5050 with the following endpoints:

### POST /execute/text

Submit Python code as plain text in the request body.

```bash
curl -X POST http://localhost:5050/execute/text -d 'result = 2 + 3'
```

### POST /execute/image

Upload an image containing Python code. The server extracts text via OCR and executes it.

```bash
curl -X POST http://localhost:5050/execute/image -F file=@code.png
```

### POST /execute/pdf

Upload a PDF containing Python code. The server extracts text and executes it.

```bash
curl -X POST http://localhost:5050/execute/pdf -F file=@code.pdf
```

### POST /execute/audio

Submit URL-encoded audio bytes in the request body. The server decodes the audio, transcribes it via Google Speech Recognition, converts the transcription from spoken English to Python syntax using a built-in speech-to-code converter, and executes the resulting code. The converter handles spoken keywords like "open paren", "equals", "indent", "new line", "single quote", etc.

```bash
python -c "
import urllib.parse
with open('code.wav', 'rb') as f:
    encoded = urllib.parse.quote(f.read(), safe='')
print(encoded)
" | curl -X POST http://localhost:5050/execute/audio -d @-
```

### POST /execute/audio-zip

Upload a ZIP file containing an audio file (.wav, .flac, .aiff). The server extracts the first audio file from the archive, transcribes it, converts the transcription to Python via the speech-to-code converter, and executes the result.

```bash
curl -X POST http://localhost:5050/execute/audio-zip -F file=@code.zip
```

### GET /health

Health check endpoint.

## Testing

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

Test fixtures (images, PDFs, audio files) are in `tests/fixtures/`.

## Response Format

All execution endpoints return JSON:

```json
{
  "success": true,
  "output": "printed output here",
  "result": "value of 'result' variable"
}
```

On failure:

```json
{
  "success": false,
  "output": "",
  "error": "error description"
}
```

## Dependencies

- **flask** — HTTP server
- **RestrictedPython** — Python sandbox compiler
- **Pillow** — Image processing for OCR pipeline
- **pytesseract** — Tesseract OCR wrapper
- **pypdf** — PDF text extraction
- **SpeechRecognition** — Audio transcription via Google Speech API
