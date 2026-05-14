import os
import signal
import tempfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from analyzer import analyze_song
import config

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB upload limit


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    # Save to temp file, preserving extension
    suffix = Path(file.filename).suffix or ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp)
        tmp_path = tmp.name

    try:
        duration = int(request.form.get("duration", 0))
    except (ValueError, TypeError):
        duration = 60
    if duration <= 0:
        duration = 0  # 0 = full song

    try:
        result = analyze_song(tmp_path, original_filename=file.filename, duration=duration)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        os.unlink(tmp_path)
        return jsonify({"error": f"Analysis crashed: {exc}"}), 500
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    status = 200 if result["error"] is None else 400
    return jsonify(result), status


@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(config.load())


@app.route("/api/settings", methods=["POST"])
def save_settings():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    cfg = config.load()
    if "default_directory" in data:
        cfg["default_directory"] = data["default_directory"]
    if "analysis_duration" in data:
        try:
            cfg["analysis_duration"] = int(data["analysis_duration"])
        except (ValueError, TypeError):
            pass
    config.save(cfg)
    return jsonify(cfg)


@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    import threading
    def _exit():
        os._exit(0)
    # Send response first, then exit after a short delay
    threading.Timer(0.5, _exit).start()
    return jsonify({"status": "shutting down"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
