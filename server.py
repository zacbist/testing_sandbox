import io
import zipfile
import urllib.parse

from flask import Flask, request, jsonify
from RestrictedPython import compile_restricted, safe_builtins
from PIL import Image
import pytesseract
from pypdf import PdfReader
import speech_recognition as sr

app = Flask(__name__)

BLOCKED_PATTERNS = ["__import__", "exec(", "eval(", "compile(", "open("]


def validate_code(code):
    for pattern in BLOCKED_PATTERNS:
        if pattern in code:
            return False, f"Blocked pattern: {pattern}"
    return True, None


def execute_sandboxed(code):
    valid, msg = validate_code(code)
    if not valid:
        return {"success": False, "output": "", "error": msg}

    try:
        byte_code = compile_restricted(code, "<sandbox>", "exec")
    except SyntaxError as e:
        return {"success": False, "output": "", "error": f"SyntaxError: {e}"}

    sandbox_builtins = dict(safe_builtins)
    sandbox_builtins["getattr"] = getattr
    sandbox_builtins["setattr"] = setattr
    sandbox_builtins["hasattr"] = hasattr
    sandbox_builtins["type"] = type
    sandbox_builtins["isinstance"] = isinstance
    sandbox_builtins["chr"] = chr
    sandbox_builtins["ord"] = ord
    sandbox_builtins["print"] = print
    sandbox_builtins["str"] = str
    sandbox_builtins["int"] = int
    sandbox_builtins["float"] = float
    sandbox_builtins["list"] = list
    sandbox_builtins["dict"] = dict
    sandbox_builtins["tuple"] = tuple
    sandbox_builtins["set"] = set
    sandbox_builtins["len"] = len
    sandbox_builtins["range"] = range
    sandbox_builtins["sum"] = sum
    sandbox_builtins["min"] = min
    sandbox_builtins["max"] = max
    sandbox_builtins["abs"] = abs
    sandbox_builtins["round"] = round
    sandbox_builtins["sorted"] = sorted
    sandbox_builtins["enumerate"] = enumerate
    sandbox_builtins["zip"] = zip
    sandbox_builtins["map"] = map
    sandbox_builtins["filter"] = filter

    printed_output = []

    class PrintCollector:
        def __init__(self, _getattr_=None):
            self._output = printed_output
        def write(self, text):
            self._output.append(text)
        def __call__(self):
            return "".join(self._output)
        def _call_print(self, *args, **kwargs):
            sep = kwargs.get("sep", " ")
            end = kwargs.get("end", "\n")
            text = sep.join(str(a) for a in args) + end
            self._output.append(text)

    namespace = {
        "__builtins__": sandbox_builtins,
        "_getattr_": getattr,
        "_getiter_": iter,
        "_getitem_": lambda obj, key: obj[key],
        "_write_": lambda x: x,
        "_inplacevar_": lambda op, x, y: op(x, y),
        "_print_": PrintCollector,
        "result": None,
    }

    try:
        exec(byte_code, namespace)
        output = "".join(printed_output)
        return {
            "success": True,
            "output": output,
            "result": str(namespace.get("result", "")),
        }
    except Exception as e:
        return {"success": False, "output": "".join(printed_output), "error": str(e)}


def extract_from_image(file_stream):
    image = Image.open(file_stream)
    return pytesseract.image_to_string(image)


def extract_from_pdf(file_stream):
    reader = PdfReader(file_stream)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def transcribe_audio(audio_bytes):
    recognizer = sr.Recognizer()
    audio_file = io.BytesIO(audio_bytes)
    with sr.AudioFile(audio_file) as source:
        audio_data = recognizer.record(source)
    return recognizer.recognize_google(audio_data)


SPEECH_SYMBOLS = [
    ("open paren", "("),
    ("close paren", ")"),
    ("open bracket", "["),
    ("close bracket", "]"),
    ("open brace", "{"),
    ("close brace", "}"),
    ("double underscore", "__"),
    ("underscore", "_"),
    ("single quote", "'"),
    ("double quote", '"'),
    ("equals", "="),
    ("colon", ":"),
    ("comma", ","),
    ("dot", "."),
    ("plus", "+"),
    ("minus", "-"),
    ("times", "*"),
    ("divided by", "/"),
    ("modulo", "%"),
    ("hashtag", "#"),
    ("at sign", "@"),
    ("exclamation", "!"),
    ("semicolon", ";"),
]


def speech_to_code(text):
    import re
    text = text.replace("new line", "\n").replace("newline", "\n")
    text = re.sub(r' *\n *', '\n', text)
    text = text.replace("four spaces", "    ").replace("indent", "    ")
    for spoken, symbol in SPEECH_SYMBOLS:
        text = text.replace(spoken, symbol)
    lines = text.split("\n")
    result = []
    for line in lines:
        line = line.rstrip()
        line = re.sub(r'\s*__\s*', '__', line)
        line = re.sub(r'(\w)\s+_\s*(\w)', r'\1_\2', line)
        line = re.sub(r'\s*\(\s*', '(', line)
        line = re.sub(r'\s*\)\s*', ')', line)
        line = re.sub(r'\s*\[\s*', '[', line)
        line = re.sub(r'\s*\]\s*', ']', line)
        line = re.sub(r'\s*\.\s*', '.', line)
        line = re.sub(r"\s*'\s*", "'", line)
        line = re.sub(r'\s*"\s*', '"', line)
        line = re.sub(r'\s*,\s*', ', ', line)
        line = re.sub(r'\s*:\s*$', ':', line)
        line = re.sub(r'\s+=\s+', ' = ', line)
        line = re.sub(r'=\s+=', '==', line)
        result.append(line)
    return "\n".join(result)


@app.route("/execute/text", methods=["POST"])
def execute_text():
    code = request.get_data(as_text=True)
    if not code.strip():
        return jsonify({"success": False, "output": "", "error": "Empty code"}), 400
    return jsonify(execute_sandboxed(code))


@app.route("/execute/image", methods=["POST"])
def execute_image():
    if "file" not in request.files:
        return jsonify({"success": False, "output": "", "error": "No file"}), 400
    code = extract_from_image(request.files["file"].stream)
    if not code.strip():
        return jsonify({"success": False, "output": "", "error": "No code in image"}), 400
    return jsonify(execute_sandboxed(code))


@app.route("/execute/pdf", methods=["POST"])
def execute_pdf():
    if "file" not in request.files:
        return jsonify({"success": False, "output": "", "error": "No file"}), 400
    code = extract_from_pdf(request.files["file"].stream)
    if not code.strip():
        return jsonify({"success": False, "output": "", "error": "No code in PDF"}), 400
    return jsonify(execute_sandboxed(code))


@app.route("/execute/audio", methods=["POST"])
def execute_audio():
    encoded_data = request.get_data(as_text=True)
    if not encoded_data.strip():
        return jsonify({"success": False, "output": "", "error": "Empty data"}), 400
    try:
        audio_bytes = urllib.parse.unquote_to_bytes(encoded_data)
    except Exception as e:
        return jsonify({"success": False, "output": "", "error": str(e)}), 400
    try:
        raw_text = transcribe_audio(audio_bytes)
    except sr.UnknownValueError:
        return jsonify({"success": False, "output": "", "error": "Could not understand audio"})
    except sr.RequestError as e:
        return jsonify({"success": False, "output": "", "error": str(e)})
    code = speech_to_code(raw_text)
    if not code.strip():
        return jsonify({"success": False, "output": "", "error": "No code from audio"}), 400
    return jsonify(execute_sandboxed(code))


@app.route("/execute/audio-zip", methods=["POST"])
def execute_audio_zip():
    if "file" not in request.files:
        return jsonify({"success": False, "output": "", "error": "No file"}), 400
    try:
        zf = zipfile.ZipFile(request.files["file"].stream)
    except zipfile.BadZipFile:
        return jsonify({"success": False, "output": "", "error": "Invalid zip file"}), 400
    audio_files = [n for n in zf.namelist() if n.endswith((".wav", ".flac", ".aiff"))]
    if not audio_files:
        return jsonify({"success": False, "output": "", "error": "No audio file in zip"}), 400
    audio_bytes = zf.read(audio_files[0])
    try:
        raw_text = transcribe_audio(audio_bytes)
    except sr.UnknownValueError:
        return jsonify({"success": False, "output": "", "error": "Could not understand audio"})
    except sr.RequestError as e:
        return jsonify({"success": False, "output": "", "error": str(e)})
    code = speech_to_code(raw_text)
    if not code.strip():
        return jsonify({"success": False, "output": "", "error": "No code from audio"}), 400
    return jsonify(execute_sandboxed(code))


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
