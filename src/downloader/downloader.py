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
        self.current_process = None
        self.should_cancel = False
    
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
        on_progress: Callable[[dict], None] = None,
        mode: str = "auto",
        is_playlist_item: bool = False,
        convert_enabled: bool = False,
        convert_format: str = ""
    ):
        """
        Start download in a separate thread

        Args:
            yt_dlp_path: Path to yt-dlp executable
            url: Video URL to download
            output_dir: Output directory for downloaded files
            format_type: Format type ('mp4', 'mp3', etc.)
            quality: Quality selection ('best', '1080', '720', '480', '360', 'worst')
            trim_start: Start time for trimming (HH:MM:SS format) or None
            trim_end: End time for trimming (HH:MM:SS format) or None
            on_log: Callback function for logging messages
            on_complete: Callback function when download completes
            on_error: Callback function when download fails
            on_download_started: Optional callback when actual download starts
            on_progress: Optional callback for progress dict with keys: 'percent', 'speed', 'eta', 'downloaded', 'total'
            mode: Download mode ('video', 'audio', or 'auto')
            is_playlist_item: Whether this is part of a playlist download
            convert_enabled: Whether to convert after download
            convert_format: Target format for conversion
        """
        if self.is_downloading and not is_playlist_item:
            on_error("A download is already in progress")
            return

        # Reset cancel flag
        self.should_cancel = False

        # Start download in separate thread
        thread = threading.Thread(
            target=self._download_thread,
            args=(yt_dlp_path, url, output_dir, format_type, quality, trim_start, trim_end, on_log, on_complete, on_error, on_download_started, on_progress, mode, convert_enabled, convert_format),
            daemon=True
        )
        thread.start()

    def cancel_download(self):
        """Cancel the current download"""
        self.should_cancel = True
        if self.current_process:
            try:
                self.current_process.terminate()
                # Give it a moment to terminate gracefully
                import time
                time.sleep(0.5)
                if self.current_process.poll() is None:
                    # If still running, force kill
                    self.current_process.kill()
            except Exception:
                pass
    
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
        on_progress: Callable[[dict], None] = None,
        mode: str = "auto",
        convert_enabled: bool = False,
        convert_format: str = ""
    ):
        """
        Execute download in background thread

        Args:
            yt_dlp_path: Path to yt-dlp executable
            url: Video URL to download
            output_dir: Output directory for downloaded files
            format_type: Format type ('mp4', 'mp3', etc.)
            quality: Quality selection ('best', '1080', '720', '480', '360', 'worst')
            trim_start: Start time for trimming (HH:MM:SS format) or None
            trim_end: End time for trimming (HH:MM:SS format) or None
            on_log: Callback function for logging messages
            on_complete: Callback function when download completes
            on_error: Callback function when download fails
            on_download_started: Optional callback when actual download starts
            on_progress: Optional callback for progress dict with keys: 'percent', 'speed', 'eta', 'downloaded', 'total'
            mode: Download mode ('video', 'audio', or 'auto')
            convert_enabled: Whether to convert after download
            convert_format: Target format for conversion
        """
        self.is_downloading = True
        download_started = False

        try:
            # Determine if we should skip embedding thumbnail (will be done after trimming)
            skip_thumbnail_embed = bool(trim_start or trim_end)

            # Build command based on format
            cmd = self._build_command(yt_dlp_path, url, output_dir, format_type, quality, trim_start, trim_end, skip_thumbnail_embed, mode, convert_enabled, convert_format)

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

            # Store process reference for cancellation
            self.current_process = process

            # Read output line by line
            for line in process.stdout:
                # Check if download was cancelled
                if self.should_cancel:
                    process.terminate()
                    on_log("\n✗ Download cancelled by user")
                    break

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

            # Check if download was cancelled
            if self.should_cancel:
                on_error("Download cancelled by user")
            elif process.returncode == 0:
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
                            on_log,
                            output_dir
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
            self.current_process = None

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

    def _build_command(self, yt_dlp_path: str, url: str, output_dir: str, format_type: str, quality: str, trim_start: Optional[str], trim_end: Optional[str], skip_thumbnail_embed: bool = False, mode: str = "auto", convert_enabled: bool = False, convert_format: str = "") -> list:
        """
        Build yt-dlp command based on format type and quality

        Args:
            yt_dlp_path: Path to yt-dlp executable
            url: Video URL to download
            output_dir: Output directory for downloaded files
            format_type: Format type ('mp4', 'mkv', 'avi', 'mov', 'mp3', 'wav', 'aac', 'm4a', etc.)
            quality: Quality selection ('best', '1080', '720', '480', '360', 'worst', or specific resolution)
            skip_thumbnail_embed: If True, download thumbnail but don't embed it (for trimming)
            mode: Download mode ('video', 'audio', or 'auto')
            convert_enabled: Whether to convert after download
            convert_format: Target format for conversion

        Returns:
            List of command arguments
        """
        # Suppress unused parameter warnings - these are kept for API compatibility
        _ = trim_start
        _ = trim_end

        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
        format_type_lower = format_type.lower()

        # Audio-only formats
        audio_formats = ['mp3', 'wav', 'aac', 'm4a', 'opus', 'vorbis', 'flac', 'ogg']

        if format_type_lower in audio_formats or mode == "audio":
            # Extract audio and convert to specified format
            # Use convert format if enabled, otherwise use format_type
            audio_output_format = convert_format.lower() if convert_enabled and convert_format else format_type_lower

            cmd = [
                yt_dlp_path,
                "-x",
                "--audio-format", audio_output_format,
                "--audio-quality", "0",
                "--embed-metadata",
            ]

            # Handle thumbnail based on trimming
            if skip_thumbnail_embed:
                # Download thumbnail but don't embed it yet (will be embedded after trimming)
                cmd.append("--write-thumbnail")
            else:
                # Embed thumbnail directly
                cmd.append("--embed-thumbnail")
                # Add thumbnail conversion for formats that support it
                if audio_output_format in ['mp3', 'aac', 'm4a']:
                    cmd.extend([
                        "--ppa", "ThumbnailsConvertor+ffmpeg_o:-c:v mjpeg -vf crop=\"'if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'\"",
                    ])

            cmd.extend(["-o", output_template, url])
            return cmd

        else:
            # Video formats
            # For video-only mode, use video-only format string
            if mode == "video":
                format_str = self._get_video_only_format_string(quality)
            else:
                format_str = self._get_video_format_string(quality)

            cmd = [
                yt_dlp_path,
                "-f", format_str,
            ]

            # Set merge output format for video formats
            if format_type_lower in ['mp4', 'mkv', 'avi', 'mov', 'flv', 'webm']:
                cmd.extend(["--merge-output-format", format_type_lower])

            cmd.extend([
                "--embed-metadata",
            ])

            # Handle thumbnail based on trimming
            if skip_thumbnail_embed:
                # Download thumbnail but don't embed it yet (will be embedded after trimming)
                cmd.append("--write-thumbnail")
            else:
                # Embed thumbnail directly
                cmd.append("--embed-thumbnail")

            # Add conversion option if enabled (for video modes)
            if convert_enabled and convert_format:
                convert_format_lower = convert_format.lower()
                # Video conversion formats
                video_convert_formats = ['mp4', 'mkv', 'avi', 'mov', 'webm', 'flv']
                if convert_format_lower in video_convert_formats:
                    cmd.extend(["--recode-video", convert_format_lower])

            cmd.extend([
                "-o", output_template,
                url
            ])

            return cmd

    def _get_video_format_string(self, quality: str) -> str:
        """
        Get yt-dlp format string based on quality selection

        Args:
            quality: Quality selection ('best', '1080', '720', '480', '360', 'worst', or with fps like '1080_25fps')

        Returns:
            Format string for yt-dlp
        """
        if quality == "best":
            return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        elif quality == "worst":
            return "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst"
        else:
            # Specific resolution (e.g., 1080, 720, 480, 360, or with fps like 1080_25fps)
            # Extract resolution and fps if included
            parts = quality.split('_')
            resolution = parts[0]

            # Build format string with optional fps filter
            if len(parts) > 1 and parts[1].endswith('fps'):
                # Extract fps number (e.g., "25fps" -> "25")
                fps = parts[1].rstrip('fps')
                # Include fps filter for more precise selection
                return f"bestvideo[height<={resolution}][fps={fps}][ext=mp4]+bestaudio[ext=m4a]/best[height<={resolution}][fps={fps}][ext=mp4]/best"
            else:
                # No fps specified, just use resolution
                return f"bestvideo[height<={resolution}][ext=mp4]+bestaudio[ext=m4a]/best[height<={resolution}][ext=mp4]/best"

    def _get_video_only_format_string(self, quality: str) -> str:
        """
        Get yt-dlp format string for video-only (no audio)

        Args:
            quality: Quality selection ('best', '1080', '720', '480', '360', 'worst', or with fps like '1080_25fps')

        Returns:
            Format string for yt-dlp (video only)
        """
        if quality == "best":
            return "bestvideo[ext=mp4]/best[ext=mp4]/bestvideo/best"
        elif quality == "worst":
            return "worstvideo[ext=mp4]/worst[ext=mp4]/worstvideo/worst"
        else:
            # Specific resolution (e.g., 1080, 720, 480, 360, or with fps like 1080_25fps)
            # Extract resolution and fps if included
            parts = quality.split('_')
            resolution = parts[0]

            # Build format string with optional fps filter (video only)
            if len(parts) > 1 and parts[1].endswith('fps'):
                # Extract fps number (e.g., "25fps" -> "25")
                fps = parts[1].rstrip('fps')
                # Include fps filter for more precise selection
                return f"bestvideo[height<={resolution}][fps={fps}][ext=mp4]/best[height<={resolution}][fps={fps}][ext=mp4]/bestvideo[height<={resolution}][fps={fps}]/best"
            else:
                # No fps specified, just use resolution
                return f"bestvideo[height<={resolution}][ext=mp4]/best[height<={resolution}][ext=mp4]/bestvideo[height<={resolution}]/best"

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

        # Look for all common media files (not just mp4 and mp3)
        patterns = [
            os.path.join(output_dir, "*.mp4"),
            os.path.join(output_dir, "*.mp3"),
            os.path.join(output_dir, "*.opus"),
            os.path.join(output_dir, "*.wav"),
            os.path.join(output_dir, "*.aac"),
            os.path.join(output_dir, "*.m4a"),
            os.path.join(output_dir, "*.mkv"),
            os.path.join(output_dir, "*.avi"),
            os.path.join(output_dir, "*.mov"),
            os.path.join(output_dir, "*.flv"),
            os.path.join(output_dir, "*.webm"),
            os.path.join(output_dir, "*.flac"),
        ]

        files = []
        for pattern in patterns:
            files.extend(glob.glob(pattern))

        if not files:
            return None

        # Return the most recently modified file
        return max(files, key=os.path.getmtime)

    def _find_thumbnail_file(self, input_file: str, output_dir: str) -> Optional[str]:
        """
        Find thumbnail file downloaded by yt-dlp

        Args:
            input_file: Path to downloaded media file
            output_dir: Output directory where thumbnail should be

        Returns:
            Path to thumbnail file or None if not found
        """
        try:
            import glob
            base, ext = os.path.splitext(input_file)
            base_name = os.path.basename(base)

            # Look for thumbnail files with common extensions
            thumbnail_patterns = [
                os.path.join(output_dir, f"{base_name}.jpg"),
                os.path.join(output_dir, f"{base_name}.png"),
                os.path.join(output_dir, f"{base_name}.webp"),
            ]

            for pattern in thumbnail_patterns:
                if os.path.exists(pattern):
                    return pattern

            # Also try glob pattern for any image files with same base name
            for ext_pattern in ['*.jpg', '*.png', '*.webp']:
                files = glob.glob(os.path.join(output_dir, f"{base_name}.{ext_pattern.split('.')[-1]}"))
                if files:
                    return files[0]

            return None

        except Exception as e:
            return None

    def _embed_thumbnail(self, input_file: str, thumbnail_file: str, on_log) -> bool:
        """
        Embed thumbnail into audio file

        Args:
            input_file: Path to audio file
            thumbnail_file: Path to thumbnail image
            on_log: Logging callback

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(thumbnail_file):
                on_log(f"⚠ Thumbnail file not found, skipping re-embedding")
                return True

            base, ext = os.path.splitext(input_file)
            output_file = f"{base}_with_thumb{ext}"

            # Use FFmpeg to embed thumbnail
            cmd = [
                "ffmpeg", "-y",
                "-i", input_file,
                "-i", thumbnail_file,
                "-c", "copy",
                "-map", "0",
                "-map", "1",
                "-c:v", "mjpeg",
                "-disposition:v:1", "attached_pic",
                output_file
            ]

            on_log(f"Re-embedding thumbnail...")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # Read stderr to capture FFmpeg output
            for line in process.stderr:
                line = line.rstrip()
                if line and "frame=" in line:
                    on_log(line)

            process.wait()

            if process.returncode == 0:
                # Replace original file with thumbnail-embedded version
                os.remove(input_file)
                os.rename(output_file, input_file)
                on_log(f"✓ Thumbnail re-embedded")
                return True
            else:
                on_log(f"⚠ Failed to re-embed thumbnail (code: {process.returncode})")
                # Clean up failed output file if it exists
                if os.path.exists(output_file):
                    os.remove(output_file)
                return False

        except Exception as e:
            on_log(f"⚠ Thumbnail embedding error: {str(e)}")
            return False

    def _trim_with_ffmpeg(
        self,
        input_file: str,
        start_time: Optional[str],
        end_time: Optional[str],
        on_log: Callable[[str], None],
        output_dir: Optional[str] = None
    ) -> bool:
        """
        Trim video/audio file using FFmpeg, preserving thumbnails for audio files

        Args:
            input_file: Path to input file
            start_time: Start time (HH:MM:SS) or None
            end_time: End time (HH:MM:SS) or None
            on_log: Logging callback
            output_dir: Output directory (used to find thumbnail file)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if this is an audio file (has embedded thumbnail)
            base, ext = os.path.splitext(input_file)
            ext_lower = ext.lower()
            is_audio_format = ext_lower in ['.mp3', '.aac', '.m4a', '.opus', '.wav', '.flac']

            # Find thumbnail file downloaded by yt-dlp (if trimming was enabled)
            thumbnail_file = None
            if is_audio_format and output_dir:
                thumbnail_file = self._find_thumbnail_file(input_file, output_dir)
                if thumbnail_file:
                    on_log(f"Found thumbnail: {os.path.basename(thumbnail_file)}")

            # Create output filename
            output_file = f"{base}_trimmed{ext}"

            # Build FFmpeg command
            cmd = ["ffmpeg", "-y", "-i", input_file]

            # Add start time if specified (after input for accurate seeking)
            if start_time and start_time != "00:00:00":
                cmd.extend(["-ss", start_time])

            # Add end time if specified
            if end_time and end_time != "00:00:00":
                cmd.extend(["-to", end_time])

            # Copy streams without re-encoding for speed
            # Use -map_metadata to preserve metadata
            cmd.extend([
                "-c", "copy",
                "-map_metadata", "0",
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

                # Re-embed thumbnail for audio files
                if is_audio_format and thumbnail_file:
                    self._embed_thumbnail(input_file, thumbnail_file, on_log)
                    # Clean up thumbnail file
                    try:
                        if os.path.exists(thumbnail_file):
                            os.remove(thumbnail_file)
                    except Exception as e:
                        on_log(f"⚠ Could not clean up thumbnail file: {str(e)}")

                return True
            else:
                on_log(f"✗ FFmpeg failed with code: {process.returncode}")
                # Clean up failed output file if it exists
                if os.path.exists(output_file):
                    os.remove(output_file)
                # Clean up thumbnail file if extraction was done
                if thumbnail_file and os.path.exists(thumbnail_file):
                    try:
                        os.remove(thumbnail_file)
                    except Exception as e:
                        on_log(f"⚠ Could not clean up thumbnail file: {str(e)}")
                return False

        except FileNotFoundError:
            on_log("✗ FFmpeg not found. Please install FFmpeg and add it to PATH")
            on_log("  Download from: https://ffmpeg.org/download.html")
            return False
        except Exception as e:
            on_log(f"✗ Trim error: {str(e)}")
            return False

