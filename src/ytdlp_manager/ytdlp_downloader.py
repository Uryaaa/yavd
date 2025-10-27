"""yt-dlp downloader for getting different versions from GitHub"""

import urllib.request
import json
import os
import threading
import time
from typing import Callable, Optional
from pathlib import Path


class YtdlpDownloader:
    """Downloads yt-dlp executable from GitHub"""
    
    # GitHub API URLs
    STABLE_RELEASE_URL = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
    NIGHTLY_RELEASE_URL = "https://api.github.com/repos/yt-dlp/yt-dlp-nightly-builds/releases/latest"
    MASTER_DOWNLOAD_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
    
    def __init__(self):
        """Initialize yt-dlp downloader"""
        self.is_downloading = False
    
    def download(
        self,
        version_type: str,
        output_path: str,
        on_progress: Callable[[dict], None],
        on_log: Callable[[str], None],
        on_complete: Callable[[str], None],
        on_error: Callable[[str], None]
    ):
        """
        Download yt-dlp executable

        Args:
            version_type: Type of version ('stable', 'nightly', 'master')
            output_path: Path where to save the executable
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
            args=(version_type, output_path, on_progress, on_log, on_complete, on_error),
            daemon=True
        )
        thread.start()
    
    def _download_thread(
        self,
        version_type: str,
        output_path: str,
        on_progress: Callable[[int, int], None],
        on_log: Callable[[str], None],
        on_complete: Callable[[str], None],
        on_error: Callable[[str], None]
    ):
        """Execute download in background thread"""
        self.is_downloading = True
        
        try:
            # Get download URL based on version type
            on_log(f"Fetching {version_type} version information...")
            download_url = self._get_download_url(version_type, on_log)

            if not download_url:
                on_error(f"Failed to get download URL for {version_type} version")
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
            urllib.request.urlretrieve(download_url, output_path, reporthook)
            
            # Verify file was downloaded
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                on_log(f"✓ Successfully downloaded yt-dlp ({version_type})")
                on_log(f"  File size: {os.path.getsize(output_path):,} bytes")
                on_complete(output_path)
            else:
                on_error("Download completed but file is invalid")
        
        except Exception as e:
            on_log(f"✗ Error: {str(e)}")
            on_error(str(e))
        
        finally:
            self.is_downloading = False
    
    def _get_download_url(self, version_type: str, on_log: Callable[[str], None]) -> Optional[str]:
        """
        Get download URL for specified version type
        
        Args:
            version_type: Type of version ('stable', 'nightly', 'master')
            on_log: Logging callback
            
        Returns:
            Download URL or None if failed
        """
        try:
            if version_type == "master":
                # Master build uses direct download URL
                return self.MASTER_DOWNLOAD_URL
            
            # For stable and nightly, query GitHub API
            api_url = self.STABLE_RELEASE_URL if version_type == "stable" else self.NIGHTLY_RELEASE_URL
            
            # Create request with User-Agent header (required by GitHub API)
            req = urllib.request.Request(
                api_url,
                headers={'User-Agent': 'yt-dlp-gui'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            # Find the Windows executable asset
            assets = data.get('assets', [])
            for asset in assets:
                name = asset.get('name', '').lower()
                if name == 'yt-dlp.exe' or name.endswith('yt-dlp.exe'):
                    download_url = asset.get('browser_download_url')
                    version = data.get('tag_name', 'unknown')
                    on_log(f"Found version: {version}")
                    return download_url
            
            on_log("⚠ Could not find yt-dlp.exe in release assets")
            return None
        
        except Exception as e:
            on_log(f"✗ Error fetching release info: {str(e)}")
            return None
    
    def get_version_info(self, version_type: str) -> Optional[dict]:
        """
        Get version information without downloading
        
        Args:
            version_type: Type of version ('stable', 'nightly', 'master')
            
        Returns:
            Dictionary with version info or None
        """
        try:
            if version_type == "master":
                return {
                    'version': 'master',
                    'description': 'Latest master branch build'
                }
            
            api_url = self.STABLE_RELEASE_URL if version_type == "stable" else self.NIGHTLY_RELEASE_URL
            
            req = urllib.request.Request(
                api_url,
                headers={'User-Agent': 'yt-dlp-gui'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            return {
                'version': data.get('tag_name', 'unknown'),
                'published_at': data.get('published_at', ''),
                'description': data.get('name', ''),
                'body': data.get('body', '')
            }
        
        except Exception:
            return None

