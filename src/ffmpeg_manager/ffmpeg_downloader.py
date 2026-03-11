"""FFmpeg downloader for getting FFmpeg from GitHub releases"""

import urllib.request
import json
import os
import threading
import zipfile
import time
from typing import Callable, Optional
from pathlib import Path


class FFmpegDownloader:
    """Downloads FFmpeg executable from GitHub"""
    
    # GitHub API URL for FFmpeg releases
    RELEASES_URL = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases"
    
    def __init__(self):
        """Initialize FFmpeg downloader"""
        self.is_downloading = False
    
    def download(
        self,
        output_path: str,
        build_variant: str,
        on_progress: Callable[[dict], None],
        on_log: Callable[[str], None],
        on_complete: Callable[[str], None],
        on_error: Callable[[str], None]
    ):
        """
        Download FFmpeg executable

        Args:
            output_path: Path where to save the executable
            build_variant: Build variant ("gpl", "lgpl", or "shared")
            on_progress: Callback for progress dict with keys: 'downloaded', 'total', 'speed', 'eta_seconds'
            on_log: Callback for logging messages
            on_complete: Callback when download completes with file path
            on_error: Callback when download fails
        """
        if self.is_downloading:
            on_error("A download is already in progress")
            return
        
        # Start download in separate thread
        thread = threading.Thread(
            target=self._download_thread,
            args=(output_path, build_variant, on_progress, on_log, on_complete, on_error),
            daemon=True
        )
        thread.start()
    
    def _download_thread(
        self,
        output_path: str,
        build_variant: str,
        on_progress: Callable[[int, int], None],
        on_log: Callable[[str], None],
        on_complete: Callable[[str], None],
        on_error: Callable[[str], None]
    ):
        """Execute download in background thread"""
        self.is_downloading = True
        
        try:
            # Get download URL
            on_log("Fetching latest FFmpeg release information...")
            download_url = self._get_download_url(build_variant, on_log)
            
            if not download_url:
                on_error("Failed to get download URL for FFmpeg")
                return
            
            on_log(f"Download URL: {download_url}")
            on_log(f"Downloading to: {output_path}")
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Track download progress with speed and ETA
            start_time = time.time()
            last_update_time = start_time
            last_downloaded = 0

            def reporthook(block_num, block_size, total_size):
                nonlocal last_update_time, last_downloaded

                downloaded = block_num * block_size
                if total_size > 0:
                    current_time = time.time()
                    elapsed = current_time - start_time

                    # Calculate speed and ETA every 0.5 seconds to avoid too many updates
                    if current_time - last_update_time >= 0.5 or downloaded >= total_size:
                        if elapsed > 0:
                            speed = downloaded / elapsed  # bytes per second
                            remaining = total_size - downloaded
                            if speed > 0:
                                eta_seconds = remaining / speed
                            else:
                                eta_seconds = 0

                            # Create progress info dict similar to video downloader
                            progress_info = {
                                'downloaded': downloaded,
                                'total': total_size,
                                'speed': speed,
                                'eta_seconds': eta_seconds
                            }
                            on_progress(progress_info)
                            last_update_time = current_time
                            last_downloaded = downloaded

            # Download the file
            temp_zip = output_path + ".zip"
            urllib.request.urlretrieve(download_url, temp_zip, reporthook)
            
            # Extract ffmpeg.exe from zip
            on_log("Extracting FFmpeg executable...")
            self._extract_ffmpeg(temp_zip, output_path, on_log)
            
            # Clean up zip file
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
            
            # Verify file was extracted
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                on_log(f"✓ Successfully downloaded FFmpeg")
                on_log(f"  File size: {os.path.getsize(output_path):,} bytes")
                on_complete(output_path)
            else:
                on_error("Download completed but file is invalid")
        
        except Exception as e:
            on_log(f"✗ Error: {str(e)}")
            on_error(str(e))
        
        finally:
            self.is_downloading = False
    
    def _get_download_url(self, build_variant: str, on_log: Callable[[str], None]) -> Optional[str]:
        """
        Get download URL for latest FFmpeg release

        Args:
            build_variant: Build variant ("gpl", "lgpl", or "shared")
            on_log: Logging callback

        Returns:
            Download URL or None if failed
        """
        try:
            # Create request with User-Agent header
            req = urllib.request.Request(
                self.RELEASES_URL,
                headers={'User-Agent': 'yt-dlp-gui'}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            # Normalize build variant
            variant = (build_variant or "gpl").strip().lower()
            if variant not in ("gpl", "lgpl", "shared"):
                variant = "gpl"

            # Find the latest release with Windows build
            for release in data:
                if release.get('prerelease'):
                    continue

                assets = release.get('assets', [])
                for asset in assets:
                    name = asset.get('name', '').lower()
                    # Look for Windows 64-bit build matching requested variant
                    if 'win64' not in name or not name.endswith('.zip'):
                        continue
                    if variant == "shared":
                        # Accept shared builds (GPL or LGPL)
                        if 'shared' not in name:
                            continue
                    elif variant == "gpl":
                        if 'gpl' not in name or 'shared' in name:
                            continue
                    else:  # lgpl
                        if 'lgpl' not in name or 'shared' in name:
                            continue

                        download_url = asset.get('browser_download_url')
                        version = release.get('tag_name', 'unknown')
                        on_log(f"Found version: {version} ({variant})")
                        return download_url

            on_log("⚠ Could not find FFmpeg Windows build in release assets")
            return None

        except Exception as e:
            on_log(f"✗ Error fetching release info: {str(e)}")
            return None
    
    def _extract_ffmpeg(self, zip_path: str, output_path: str, on_log: Callable[[str], None]):
        """
        Extract ffmpeg.exe from the downloaded zip file
        
        Args:
            zip_path: Path to the zip file
            output_path: Path where to save ffmpeg.exe
            on_log: Logging callback
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Find ffmpeg.exe in the zip
                for file_info in zip_ref.filelist:
                    if file_info.filename.endswith('ffmpeg.exe'):
                        # Extract to output path
                        with zip_ref.open(file_info) as source:
                            with open(output_path, 'wb') as target:
                                target.write(source.read())
                        on_log(f"Extracted: {file_info.filename}")
                        return
            
            raise Exception("ffmpeg.exe not found in zip file")
        
        except Exception as e:
            on_log(f"✗ Error extracting FFmpeg: {str(e)}")
            raise

