<p align="center">
  <img src="icon.png" alt="YAVDownloader" width="128" />
</p>

<h1 align="center">YAVDownloader</h1>
<p align="center">Yet Another Video Downloader — a clean GUI for yt-dlp.</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows-0078D4?logo=windows&logoColor=white" />
  <img alt="Python" src="https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white" />
  <img alt="UI" src="https://img.shields.io/badge/UI-CustomTkinter-2E7D32" />
  <img alt="License" src="https://img.shields.io/badge/license-MIT-1A237E" />
</p>

## ✨ Highlights
- 🎬 Video & audio download with quality selection
- 📂 Playlist selector
- ✂️ Trim and 🔄 remux (FFmpeg)
- 🧩 Templates and 📄 logs

## ✅ Requirements
- Python 3.12+
- `yt-dlp` executable
- `ffmpeg` (for trim/remux/convert)

## 🚀 Run (dev)
```bash
uv run python main.py
```

## 🧰 Build (Windows)
```bash
uv run pyinstaller --clean yt-dlp-gui.spec
```

## ⬇️ Download (Executable)
Get the latest build from the GitHub Releases page:

[Download from GitHub Releases](https://github.com/Uryaaa/yavd/releases)
