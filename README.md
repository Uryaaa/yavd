<p align="center">
  <img src="icon.png" alt="YAVDownloader" width="128" />
</p>

<h1 align="center">YAVDownloader</h1>
<p align="center">Yet Another Video Downloader — a not so clean GUI for yt-dlp.</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows-0078D4?logo=windows&logoColor=white" />
  <a href="https://www.python.org/">
    <img alt="Python" src="https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white" />
  </a>
  <a href="https://github.com/yt-dlp/yt-dlp">
    <img alt="yt-dlp" src="https://img.shields.io/badge/yt--dlp-repo-1A1A1A?logo=github&logoColor=white" />
  </a>
  <a href="https://ffmpeg.org/">
    <img alt="FFmpeg" src="https://img.shields.io/badge/FFmpeg-site-000000?logo=ffmpeg&logoColor=white" />
  </a>
  <a href="https://github.com/TomSchimansky/CustomTkinter">
    <img alt="UI" src="https://img.shields.io/badge/UI-CustomTkinter-2E7D32" />
  </a>
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

## 🛠️ Developing
Install dependencies first:
```bash
uv sync
```

Then run the app:
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
