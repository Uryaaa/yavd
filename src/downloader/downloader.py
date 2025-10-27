"""Download manager for yt-dlp operations"""

import subprocess
import threading
import os
from typing import Callable, Optional


class Downloader:
    """Handles yt-dlp download operations"""
    
    def __init__(self):
        """Initialize downloader"""
        self.is_downloading = False
    
    def download(
        self,
        yt_dlp_path: str,
        url: str,
        output_dir: str,
        format_type: str,
        quality: str,
        trim_start: Optional[str],
        trim_end: Optional[str],
        on_log: Callable[[str], None],
        on_complete: Callable[[], None],
        on_error: Callable[[str], None],
        on_download_started: Callable[[], None] = None,
        on_progress: Callable[[dict], None] = None
    ):
        """
        Start download in a separate thread

        Args:
            yt_dlp_path: Path to yt-dlp executable
            url: Video URL to download
            output_dir: Output directory for downloaded files
            format_type: Format type ('mp4' or 'mp3')
            quality: Quality selection ('best', '1080', '720', '480', '360', 'worst')
            trim_start: Start time for trimming (HH:MM:SS format) or None
            trim_end: End time for trimming (HH:MM:SS format) or None
            on_log: Callback function for logging messages
            on_complete: Callback function when download completes
            on_error: Callback function when download fails
            on_download_started: Optional callback when actual download starts
            on_progress: Optional callback for progress dict with keys: 'percent', 'speed', 'eta', 'downloaded', 'total'
        """
        if self.is_downloading:
            on_error("A download is already in progress")
            return

        # Start download in separate thread
        thread = threading.Thread(
            target=self._download_thread,
            args=(yt_dlp_path, url, output_dir, format_type, quality, trim_start, trim_end, on_log, on_complete, on_error, on_download_started, on_progress),
            daemon=True
        )
        thread.start()
    
    def _download_thread(
        self,
        yt_dlp_path: str,
        url: str,
        output_dir: str,
        format_type: str,
        quality: str,
        trim_start: Optional[str],
        trim_end: Optional[str],
        on_log: Callable[[str], None],
        on_complete: Callable[[], None],
        on_error: Callable[[str], None],
        on_download_started: Callable[[], None] = None,
        on_progress: Callable[[dict], None] = None
    ):
        """
        Execute download in background thread

        Args:
            yt_dlp_path: Path to yt-dlp executable
            url: Video URL to download
            output_dir: Output directory for downloaded files
            format_type: Format type ('mp4' or 'mp3')
            quality: Quality selection ('best', '1080', '720', '480', '360', 'worst')
            trim_start: Start time for trimming (HH:MM:SS format) or None
            trim_end: End time for trimming (HH:MM:SS format) or None
            on_log: Callback function for logging messages
            on_complete: Callback function when download completes
            on_error: Callback function when download fails
            on_download_started: Optional callback when actual download starts
            on_progress: Optional callback for progress dict with keys: 'percent', 'speed', 'eta', 'downloaded', 'total'
        """
        self.is_downloading = True
        download_started = False

        try:
            # Build command based on format
            cmd = self._build_command(yt_dlp_path, url, output_dir, format_type, quality, trim_start, trim_end)

            on_log(f"Executing: {' '.join(cmd)}\n")
            on_log("-" * 70)

            # Execute command and capture output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # Read output line by line
            for line in process.stdout:
                on_log(line.rstrip())

                # Detect when actual download starts
                if not download_started and on_download_started:
                    # Look for indicators that download has started
                    if any(indicator in line for indicator in [
                        'Downloading',
                        'Destination:',
                        '[download]',
                        'has already been downloaded'
                    ]):
                        download_started = True
                        on_download_started()

                # Parse progress from yt-dlp output
                if on_progress and '[download]' in line:
                    # yt-dlp output format: [download]  50.5% of ~123.45MiB at 1.23MiB/s ETA 00:30
                    import re
                    progress_info = self._parse_progress_line(line)
                    if progress_info:
                        on_progress(progress_info)

            process.wait()

            if process.returncode == 0:
                on_log("-" * 70)
                on_log("✓ Download completed successfully!")

                # If trimming is enabled, process with FFmpeg
                if trim_start or trim_end:
                    on_log("-" * 70)
                    on_log("Starting trim process with FFmpeg...")

                    # Find the downloaded file
                    downloaded_file = self._find_downloaded_file(output_dir, cmd)
                    if downloaded_file:
                        success = self._trim_with_ffmpeg(
                            downloaded_file,
                            trim_start,
                            trim_end,
                            on_log
                        )
                        if success:
                            on_log("✓ Trim completed successfully!")
                            on_complete()
                        else:
                            on_error("Trim failed - original file preserved")
                    else:
                        on_log("⚠ Could not find downloaded file for trimming")
                        on_complete()
                else:
                    on_complete()
            else:
                on_log("-" * 70)
                on_log(f"✗ Download failed with error code: {process.returncode}")
                on_error("Check the output log for details")
        
        except Exception as e:
            on_log(f"✗ Error: {str(e)}")
            on_error(str(e))
        
        finally:
            self.is_downloading = False

    def _parse_progress_line(self, line: str) -> Optional[dict]:
        """
        Parse progress information from yt-dlp output line

        Format: [download]  50.5% of ~123.45MiB at 1.23MiB/s ETA 00:30

        Args:
            line: Output line from yt-dlp

        Returns:
            Dictionary with keys: 'percent', 'speed', 'eta', 'downloaded', 'total'
            or None if parsing fails
        """
        import re

        try:
            progress_info = {}

            # Parse percentage
            percent_match = re.search(r'(\d+\.?\d*)\%', line)
            if percent_match:
                progress_info['percent'] = float(percent_match.group(1))

            # Parse downloaded and total size (e.g., "50.5% of ~123.45MiB")
            size_match = re.search(r'of\s+~?(\d+\.?\d*[KMG]iB)', line)
            if size_match:
                progress_info['total'] = size_match.group(1)

            # Parse download speed (e.g., "at 1.23MiB/s")
            speed_match = re.search(r'at\s+(\d+\.?\d*[KMG]iB/s)', line)
            if speed_match:
                progress_info['speed'] = speed_match.group(1)

            # Parse ETA (e.g., "ETA 00:30")
            eta_match = re.search(r'ETA\s+(\d+:\d+)', line)
            if eta_match:
                progress_info['eta'] = eta_match.group(1)

            # Try to extract downloaded size from the line
            # Format might be like "[download]  50.5% of ~123.45MiB at 1.23MiB/s ETA 00:30"
            # We can calculate it from percentage and total
            if 'percent' in progress_info and 'total' in progress_info:
                total_str = progress_info['total']
                # Extract numeric value and unit
                total_match = re.search(r'(\d+\.?\d*)([KMG]iB)', total_str)
                if total_match:
                    total_value = float(total_match.group(1))
                    unit = total_match.group(2)
                    percent = progress_info['percent']
                    downloaded_value = (total_value * percent) / 100
                    progress_info['downloaded'] = f"{downloaded_value:.2f}{unit}"

            return progress_info if progress_info else None

        except Exception:
            return None

    def _build_command(self, yt_dlp_path: str, url: str, output_dir: str, format_type: str, quality: str, trim_start: Optional[str], trim_end: Optional[str]) -> list:
        """
        Build yt-dlp command based on format type and quality

        Args:
            yt_dlp_path: Path to yt-dlp executable
            url: Video URL to download
            output_dir: Output directory for downloaded files
            format_type: Format type ('mp4' or 'mp3')
            quality: Quality selection ('best', '1080', '720', '480', '360', 'worst')

        Returns:
            List of command arguments
        """
        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

        if format_type == "mp4":
            # Build format string based on quality
            format_str = self._get_video_format_string(quality)

            # Download video+audio in mp4 format with metadata
            return [
                yt_dlp_path,
                "-f", format_str,
                "--merge-output-format", "mp4",
                "--embed-metadata",  # Embed title, artist, description, etc.
                "--embed-thumbnail",  # Embed thumbnail as cover art
                "-o", output_template,
                url
            ]
        else:  # mp3
            # Extract audio and convert to mp3 with metadata and thumbnail as cover art
            return [
                yt_dlp_path,
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--embed-metadata",  # Embed title, artist, description, etc.
                "--embed-thumbnail",  # Embed video thumbnail as cover art
                "--ppa", "ThumbnailsConvertor+ffmpeg_o:-c:v mjpeg -vf crop=\"'if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'\"",  # Convert thumbnail to JPEG format
                "-o", output_template,
                url
            ]

    def _get_video_format_string(self, quality: str) -> str:
        """
        Get yt-dlp format string based on quality selection

        Args:
            quality: Quality selection ('best', '1080', '720', '480', '360', 'worst')

        Returns:
            Format string for yt-dlp
        """
        if quality == "best":
            return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        elif quality == "worst":
            return "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst"
        else:
            # Specific resolution (e.g., 1080, 720, 480, 360)
            return f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best"

    def _find_downloaded_file(self, output_dir: str, cmd: list) -> Optional[str]:
        """
        Find the most recently downloaded file in output directory

        Args:
            output_dir: Output directory
            cmd: Command that was executed

        Returns:
            Path to downloaded file or None
        """
        import glob
        import time

        # Wait a moment for file system to update
        time.sleep(0.5)

        # Look for mp4 and mp3 files
        patterns = [
            os.path.join(output_dir, "*.mp4"),
            os.path.join(output_dir, "*.mp3")
        ]

        files = []
        for pattern in patterns:
            files.extend(glob.glob(pattern))

        if not files:
            return None

        # Return the most recently modified file
        return max(files, key=os.path.getmtime)

    def _trim_with_ffmpeg(
        self,
        input_file: str,
        start_time: Optional[str],
        end_time: Optional[str],
        on_log: Callable[[str], None]
    ) -> bool:
        """
        Trim video/audio file using FFmpeg

        Args:
            input_file: Path to input file
            start_time: Start time (HH:MM:SS) or None
            end_time: End time (HH:MM:SS) or None
            on_log: Logging callback

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create output filename
            base, ext = os.path.splitext(input_file)
            output_file = f"{base}_trimmed{ext}"

            # Build FFmpeg command
            cmd = ["ffmpeg", "-y", "-i", input_file]

            # Add start time if specified (before input for faster seeking)
            if start_time and start_time != "00:00:00":
                cmd.insert(1, "-ss")
                cmd.insert(2, start_time)

            # Add end time if specified
            if end_time and end_time != "00:00:00":
                cmd.extend(["-to", end_time])

            # Copy streams without re-encoding for speed
            cmd.extend([
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                output_file
            ])

            on_log(f"Trimming with FFmpeg...")
            on_log(f"Command: {' '.join(cmd)}")

            # Execute FFmpeg
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # Read stderr (FFmpeg outputs to stderr)
            for line in process.stderr:
                line = line.rstrip()
                if line:
                    on_log(line)

            process.wait()

            if process.returncode == 0:
                # Replace original file with trimmed version
                os.remove(input_file)
                os.rename(output_file, input_file)
                on_log(f"✓ File trimmed: {os.path.basename(input_file)}")
                return True
            else:
                on_log(f"✗ FFmpeg failed with code: {process.returncode}")
                # Clean up failed output file if it exists
                if os.path.exists(output_file):
                    os.remove(output_file)
                return False

        except FileNotFoundError:
            on_log("✗ FFmpeg not found. Please install FFmpeg and add it to PATH")
            on_log("  Download from: https://ffmpeg.org/download.html")
            return False
        except Exception as e:
            on_log(f"✗ Trim error: {str(e)}")
            return False

