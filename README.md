# Song Analyzer

Analyze MP3 files for their **BPM** (beats per minute) and **beat offset** (lag in milliseconds) for use in the rhythm game [Dead As Disco](https://store.steampowered.com/app/3703800/Dead_As_Disco/).

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Flask](https://img.shields.io/badge/Flask-3.1-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **Three BPM detection algorithms** (Dynamic Programming, Autocorrelation, PLP) cross-validated for accuracy
- **Confidence scoring** — high / medium / low based on agreement across methods
- **Beat offset detection** in milliseconds, with guidance when methods disagree
- **Half/double tempo detection** — flags alternative BPM when algorithms report different tempo multiples
- **Tempo variance warning** when beat intervals vary by more than 10%
- **Drag-and-drop** or native file picker for uploading songs
- **Multi-file support** — sequential processing with a progress indicator
- **Analysis history** capped at 50 entries with copy/export
- **Configurable analysis duration** — default 60 seconds, or analyze the full song
- **Persistent settings** saved to `config.json`

## Quick Start

### Prerequisites

- Python 3.12+
- Windows (the launcher script is a `.bat` file, but the server itself is cross-platform)

### Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/SongAnalyzer.git
cd SongAnalyzer

# Create a virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run

**Windows** — double-click `start.bat` (starts the server and opens your browser automatically).

**Manual** — run the Flask server directly:

```bash
python app.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## How It Works

1. Upload one or more audio files (MP3, WAV, FLAC, etc.)
2. The server analyzes the first N seconds of audio (configurable, default 60s)
3. Three independent tempo-detection algorithms run in parallel:
   - **Dynamic Programming** — `librosa.beat.beat_track`
   - **Autocorrelation** — `librosa.beat.tempo` with autocorrelation method
   - **PLP** — Predominant Local Pulse via `librosa.beat.plp`
4. Results are cross-checked: if all three agree, confidence is **high**; two agree = **medium**; none agree = **low**
5. Beat offset is derived from the method whose raw BPM best matches the consensus

## Project Structure

```
SongAnalyzer/
├── app.py              # Flask server and API routes
├── analyzer.py         # BPM/offset detection (librosa)
├── config.py           # Persistent settings (config.json)
├── requirements.txt    # Python dependencies
├── start.bat           # Windows launcher
├── templates/
│   └── index.html      # Single-page web UI
└── static/
    └── style.css       # Dark theme styling
```

## API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serves the web UI |
| `/api/analyze` | POST | Upload a file for BPM/offset analysis (multipart form, field: `file`) |
| `/api/settings` | GET | Retrieve current settings |
| `/api/settings` | POST | Update settings (JSON body) |
| `/api/shutdown` | POST | Gracefully shut down the server |

## Configuration

Settings are stored in `config.json` and can be changed from the UI settings modal:

| Setting | Default | Description |
|---|---|---|
| `default_directory` | `""` | Default folder for the file picker |
| `analysis_duration` | `60` | Seconds of audio to analyze (0 = full song) |

## Dependencies

- [Flask](https://flask.palletsprojects.com/) — lightweight web server
- [librosa](https://librosa.org/) — audio analysis
- [SoundFile](https://python-soundfile.readthedocs.io/) — audio file I/O
