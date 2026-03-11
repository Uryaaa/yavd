"""Download manager for yt-dlp operations"""

import subprocess
import threading
import os
import re
import time
import glob
import base64
from typing import Callable, Optional


class Downloader:
    """Handles yt-dlp download operations"""

    def __init__(self):
        """Initialize downloader"""
        self.is_downloading = False
        self.current_process = None
        self.should_cancel = False
        self.last_downloaded_file = None
    
    def download(
        self,
        yt_dlp_path: str,
        url: str,
        output_dir: str,
        format_type: str,
        quality: str,
        trim_start: Optional[str],
        trim_end: Optional[str],
        audio_quality: Optional[str],
        on_log: Callable[[str], None],
        on_complete: Callable[[], None],
        on_error: Callable[[str], None],
        on_download_started: Callable[[], None] = None,
        on_progress: Callable[[dict], None] = None,
        mode: str = "auto",
        is_playlist_item: bool = False,
        convert_enabled: bool = False,
        convert_format: str = "",
        save_thumbnail_file: bool = False,
        save_subtitles: bool = False,
        embed_chapters: bool = False,
        sponsorblock_enabled: bool = False,
        sponsorblock_mode: str = "mark",
        sponsorblock_categories: Optional[list] = None,
        output_template: Optional[str] = None,
        keep_original_file: bool = False,
        write_description: bool = False,
        skip_existing: bool = False,
        allow_duplicates: bool = False,
        ffmpeg_path: Optional[str] = None
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
            audio_quality: Audio bitrate/quality value ('best', 'worst', or numeric)
            on_log: Callback function for logging messages
            on_complete: Callback function when download completes
            on_error: Callback function when download fails
            on_download_started: Optional callback when actual download starts
            on_progress: Optional callback for progress dict with keys: 'percent', 'speed', 'eta', 'downloaded', 'total'
            mode: Download mode ('video', 'audio', or 'video_audio')
            is_playlist_item: Whether this is part of a playlist download
            convert_enabled: Whether to convert after download
            convert_format: Target format for conversion
            save_thumbnail_file: Whether to save thumbnail as a file
            save_subtitles: Whether to save subtitles
            embed_chapters: Whether to embed chapter metadata when available
            sponsorblock_enabled: Whether SponsorBlock removal is enabled
            sponsorblock_mode: SponsorBlock mode ("mark" or "remove")
            sponsorblock_categories: List of SponsorBlock categories to remove
            output_template: Custom yt-dlp output template path
            keep_original_file: Keep original media files after trim/remux/convert
            write_description: Save media description to .description file
            skip_existing: Skip download if output file already exists
            allow_duplicates: Allow duplicate filenames with automatic (2) suffix
            ffmpeg_path: Optional path to ffmpeg executable
        """
        if self.is_downloading and not is_playlist_item:
            on_error("A download is already in progress")
            return

        # Reset cancel flag
        self.should_cancel = False
        self.last_downloaded_file = None

        # Start download in separate thread
        thread = threading.Thread(
            target=self._download_thread,
            args=(yt_dlp_path, url, output_dir, format_type, quality, trim_start, trim_end, audio_quality, on_log, on_complete, on_error, on_download_started, on_progress, mode, convert_enabled, convert_format, save_thumbnail_file, save_subtitles, embed_chapters, sponsorblock_enabled, sponsorblock_mode, sponsorblock_categories, output_template, keep_original_file, write_description, skip_existing, allow_duplicates, ffmpeg_path),
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
        audio_quality: Optional[str],
        on_log: Callable[[str], None],
        on_complete: Callable[[], None],
        on_error: Callable[[str], None],
        on_download_started: Callable[[], None] = None,
        on_progress: Callable[[dict], None] = None,
        mode: str = "auto",
        convert_enabled: bool = False,
        convert_format: str = "",
        save_thumbnail_file: bool = False,
        save_subtitles: bool = False,
        embed_chapters: bool = False,
        sponsorblock_enabled: bool = False,
        sponsorblock_mode: str = "mark",
        sponsorblock_categories: Optional[list] = None,
        output_template: Optional[str] = None,
        keep_original_file: bool = False,
        write_description: bool = False,
        skip_existing: bool = False,
        allow_duplicates: bool = False,
        ffmpeg_path: Optional[str] = None
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
            audio_quality: Audio bitrate/quality value ('best', 'worst', or numeric)
            on_log: Callback function for logging messages
            on_complete: Callback function when download completes
            on_error: Callback function when download fails
            on_download_started: Optional callback when actual download starts
            on_progress: Optional callback for progress dict with keys: 'percent', 'speed', 'eta', 'downloaded', 'total'
            mode: Download mode ('video', 'audio', or 'video_audio')
            convert_enabled: Whether to convert after download
            convert_format: Target format for conversion
            save_thumbnail_file: Whether to save thumbnail as a file
            save_subtitles: Whether to save subtitles
            embed_chapters: Whether to embed chapter metadata when available
            sponsorblock_enabled: Whether SponsorBlock removal is enabled
            sponsorblock_mode: SponsorBlock mode ("mark" or "remove")
            sponsorblock_categories: List of SponsorBlock categories to remove
            output_template: Custom yt-dlp output template path
            keep_original_file: Keep original media files after trim/remux/convert
            write_description: Save media description to .description file
            skip_existing: Skip download if output file already exists
            allow_duplicates: Allow duplicate filenames with automatic (2) suffix
            ffmpeg_path: Optional path to ffmpeg executable
        """
        self.is_downloading = True
        download_started = False

        try:
            # Determine if we should skip embedding thumbnail (handled after trimming/convert for audio)
            audio_formats = ['mp3', 'wav', 'aac', 'm4a', 'opus', 'vorbis', 'flac', 'ogg']
            is_audio_request = (format_type.lower() in audio_formats) or (mode == "audio")
            audio_target = (convert_format.lower() if convert_enabled and convert_format else format_type.lower())
            # Skip embed when trimming; if converting, skip for non-opus audio so we can embed after convert
            skip_thumbnail_embed = bool(trim_start or trim_end) or (
                convert_enabled and is_audio_request and audio_target != "opus"
            )
            # For opus without trimming, always let yt-dlp embed the thumbnail (matches working CLI)
            if audio_target == "opus" and not trim_start and not trim_end:
                skip_thumbnail_embed = False

            effective_output_template = output_template
            if allow_duplicates:
                unique_output = self._resolve_duplicate_output_template(
                    yt_dlp_path=yt_dlp_path,
                    url=url,
                    output_template=output_template,
                    output_dir=output_dir,
                    on_log=on_log
                )
                if unique_output:
                    effective_output_template = unique_output

            # Build command based on format
            cmd = self._build_command(
                yt_dlp_path, url, output_dir, format_type, quality, trim_start, trim_end,
                skip_thumbnail_embed, mode, convert_enabled, convert_format, audio_quality,
                save_thumbnail_file, save_subtitles, embed_chapters, sponsorblock_enabled, sponsorblock_mode, sponsorblock_categories,
                effective_output_template, keep_original_file, write_description, skip_existing
            )

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

                # Find the downloaded file for post-processing
                downloaded_file = self._find_downloaded_file(output_dir, cmd)
                processing_failed = False
                current_file = downloaded_file

                # If trimming is enabled, process with FFmpeg
                if current_file and (trim_start or trim_end):
                    on_log("-" * 70)
                    on_log("Starting trim process with FFmpeg...")

                    trimmed_file = self._trim_with_ffmpeg(
                        current_file,
                        trim_start,
                        trim_end,
                        on_log,
                        output_dir,
                        keep_original_file=keep_original_file,
                        save_thumbnail_file=save_thumbnail_file,
                        ffmpeg_path=ffmpeg_path
                    )
                    if trimmed_file:
                        current_file = trimmed_file
                        on_log("✓ Trim completed successfully!")
                    else:
                        on_error("Trim failed - original file preserved")
                        processing_failed = True

                # If conversion is enabled, convert with FFmpeg
                # Skip for Opus audio (let yt-dlp embed thumbnail directly)
                if current_file and convert_enabled and convert_format and not processing_failed and not (is_audio_request and audio_target == "opus"):
                    on_log("-" * 70)
                    on_log("Starting conversion with FFmpeg...")

                    converted_file = self._convert_with_ffmpeg(
                        current_file,
                        convert_format,
                        on_log,
                        output_dir,
                        keep_original_file=keep_original_file,
                        save_thumbnail_file=save_thumbnail_file,
                        ffmpeg_path=ffmpeg_path
                    )
                    if converted_file:
                        current_file = converted_file
                        on_log("✓ Conversion completed successfully!")
                    else:
                        on_error("Conversion failed - file may be partially processed")
                        processing_failed = True

                if not processing_failed:
                    if not current_file:
                        on_log("⚠ Could not find downloaded file for processing")
                    self.last_downloaded_file = current_file
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
            if 'percent' in progress_info and 'total' in progress_info:
                total_str = progress_info['total']
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

    def _build_command(self, yt_dlp_path: str, url: str, output_dir: str, format_type: str, quality: str, trim_start: Optional[str], trim_end: Optional[str], skip_thumbnail_embed: bool = False, mode: str = "video_audio", convert_enabled: bool = False, convert_format: str = "", audio_quality: Optional[str] = None, save_thumbnail_file: bool = False, save_subtitles: bool = False, embed_chapters: bool = False, sponsorblock_enabled: bool = False, sponsorblock_mode: str = "mark", sponsorblock_categories: Optional[list] = None, output_template: Optional[str] = None, keep_original_file: bool = False, write_description: bool = False, skip_existing: bool = False) -> list:
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
            audio_quality: Audio bitrate/quality value ('best', 'worst', or numeric)
            save_thumbnail_file: Whether to save thumbnail as a file
            save_subtitles: Whether to save subtitles
            embed_chapters: Whether to embed chapter metadata when available
            sponsorblock_enabled: Whether SponsorBlock removal is enabled
            sponsorblock_mode: SponsorBlock mode ("mark" or "remove")
            sponsorblock_categories: List of SponsorBlock categories to remove
            output_template: Custom output template path
            keep_original_file: Keep intermediate files after processing
            write_description: Write media description to file
            skip_existing: Do not overwrite existing files

        Returns:
            List of command arguments
        """
        # Suppress unused parameter warnings
        _ = trim_start
        _ = trim_end

        output_template = output_template or os.path.join(output_dir, "%(title)s.%(ext)s")
        format_type_lower = format_type.lower()
        sponsorblock_categories = sponsorblock_categories or []
        audio_quality_value = self._normalize_audio_quality(audio_quality)

        # Audio-only formats
        audio_formats = ['mp3', 'wav', 'aac', 'm4a', 'opus', 'vorbis', 'flac', 'ogg']

        if format_type_lower in audio_formats or mode == "audio":
            # Extract audio and convert to specified format
            audio_output_format = convert_format.lower() if convert_enabled and convert_format else format_type_lower

            cmd = [
                yt_dlp_path,
                "-x",
                "--audio-format", audio_output_format,
                "--audio-quality", audio_quality_value,
                "--embed-metadata",
                "--compat-options", "no-youtube-unavailable-videos",
            ]
            if embed_chapters:
                cmd.append("--embed-chapters")

            # Handle thumbnail based on trimming
            if skip_thumbnail_embed:
                # Download thumbnail but don't embed it yet (will be embedded after trimming)
                cmd.append("--write-thumbnail")
                # Also write thumbnail to a temporary file for later embedding
                cmd.extend(["--convert-thumbnails", "jpg"])
            else:
                # Embed thumbnail directly
                cmd.append("--embed-thumbnail")
                # Add thumbnail conversion for formats that support it
                if audio_output_format in ['mp3', 'aac', 'm4a']:
                    cmd.extend([
                        "--ppa", "ThumbnailsConvertor+ffmpeg_o:-c:v mjpeg -vf crop=\"'if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'\"",
                    ])

            if save_thumbnail_file and "--write-thumbnail" not in cmd:
                cmd.append("--write-thumbnail")

            if save_subtitles:
                cmd.extend(["--write-subs", "--write-auto-subs"])

            if sponsorblock_enabled and sponsorblock_categories:
                flag = "--sponsorblock-remove" if sponsorblock_mode == "remove" else "--sponsorblock-mark"
                cmd.extend([flag, ",".join(sponsorblock_categories)])

            if write_description:
                cmd.append("--write-description")

            if skip_existing:
                cmd.append("--no-overwrites")

            if keep_original_file:
                cmd.append("--keep-video")

            cmd.extend(["-o", output_template, url])
            return cmd

        else:
            # Video formats
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
                "--compat-options", "no-youtube-unavailable-videos",
            ])
            if embed_chapters:
                cmd.append("--embed-chapters")

            # Handle thumbnail based on trimming (video conversions keep embedded thumbnail)
            skip_embed = skip_thumbnail_embed
            if skip_embed:
                # Download thumbnail but don't embed it yet (will be embedded after processing)
                cmd.append("--write-thumbnail")
            else:
                # Embed thumbnail directly
                cmd.append("--embed-thumbnail")

            if save_thumbnail_file and "--write-thumbnail" not in cmd:
                cmd.append("--write-thumbnail")

            if save_subtitles:
                cmd.extend(["--write-subs", "--write-auto-subs"])

            if sponsorblock_enabled and sponsorblock_categories:
                flag = "--sponsorblock-remove" if sponsorblock_mode == "remove" else "--sponsorblock-mark"
                cmd.extend([flag, ",".join(sponsorblock_categories)])

            if write_description:
                cmd.append("--write-description")

            if skip_existing:
                cmd.append("--no-overwrites")

            if keep_original_file:
                cmd.append("--keep-video")

            # Note: Conversion is now handled by FFmpeg after download, not by yt-dlp
            # This provides better control and efficiency

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
            return "bv*+ba/b"
        elif quality == "worst":
            return "wv*+wa/w"
        else:
            parts = quality.split('_')
            resolution = parts[0]

            if len(parts) > 1 and parts[1].endswith('fps'):
                fps = parts[1].rstrip('fps')
                return f"bv*[height<={resolution}][fps={fps}]+ba/b[height<={resolution}][fps={fps}]/bv[height<={resolution}][fps={fps}]+ba"
            else:
                return f"bv*[height<={resolution}]+ba/b[height<={resolution}]/bv[height<={resolution}]+ba"

    def _get_video_only_format_string(self, quality: str) -> str:
        """
        Get yt-dlp format string for video-only (no audio)

        Args:
            quality: Quality selection ('best', '1080', '720', '480', '360', 'worst', or with fps like '1080_25fps')

        Returns:
            Format string for yt-dlp (video only)
        """
        if quality == "best":
            return "bv*/b"
        elif quality == "worst":
            return "wv*/w"
        else:
            parts = quality.split('_')
            resolution = parts[0]

            if len(parts) > 1 and parts[1].endswith('fps'):
                fps = parts[1].rstrip('fps')
                return f"bv*[height<={resolution}][fps={fps}]/b[height<={resolution}][fps={fps}]/bv[height<={resolution}][fps={fps}]"
            else:
                return f"bv*[height<={resolution}]/b[height<={resolution}]/bv[height<={resolution}]"

    def _find_downloaded_file(self, output_dir: str, cmd: list) -> Optional[str]:
        """
        Find the most recently downloaded file in output directory

        Args:
            output_dir: Output directory
            cmd: Command that was executed

        Returns:
            Path to downloaded file or None
        """
        # Wait a moment for file system to update
        time.sleep(0.5)

        # Try to predict output filename from yt-dlp template
        try:
            yt_dlp_path = cmd[0] if cmd else ""
            url = cmd[-1] if cmd else ""
            template = None
            if "-o" in cmd:
                idx = cmd.index("-o")
                if idx + 1 < len(cmd):
                    template = cmd[idx + 1]
            if yt_dlp_path and url and template:
                probe_cmd = [
                    yt_dlp_path,
                    "--get-filename",
                    "--no-playlist",
                    "-o", template,
                    url
                ]
                process = subprocess.Popen(
                    probe_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding='utf-8',
                    errors='replace',
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                stdout, _ = process.communicate(timeout=20)
                if process.returncode == 0:
                    predicted_lines = (stdout or "").strip().splitlines()
                    if predicted_lines:
                        predicted_path = predicted_lines[-1].strip()
                        if predicted_path and os.path.exists(predicted_path):
                            return predicted_path
        except Exception:
            pass

        # Look for all common media files
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
            os.path.join(output_dir, "*.ogg"),
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
            base, ext = os.path.splitext(input_file)
            base_name = os.path.basename(base)

            # Look for thumbnail files with common extensions
            thumbnail_patterns = [
                os.path.join(output_dir, f"{base_name}.jpg"),
                os.path.join(output_dir, f"{base_name}.png"),
                os.path.join(output_dir, f"{base_name}.webp"),
                os.path.join(output_dir, f"{base_name}.jpeg"),
            ]

            for pattern in thumbnail_patterns:
                if os.path.exists(pattern):
                    return pattern

            # Also try glob pattern for any image files with same base name
            for ext_pattern in ['*.jpg', '*.jpeg', '*.png', '*.webp']:
                files = glob.glob(os.path.join(output_dir, f"{base_name}.{ext_pattern.split('.')[-1]}"))
                if files:
                    return files[0]

            return None

        except Exception as e:
            return None

    def _get_unique_filepath(self, file_path: str) -> str:
        """
        Build a unique path using suffix format: "name (2).ext".

        Args:
            file_path: Desired file path

        Returns:
            Non-existing file path
        """
        if not os.path.exists(file_path):
            return file_path

        base, ext = os.path.splitext(file_path)
        match = re.match(r'^(.*)\s\((\d+)\)$', base)
        if match:
            root = match.group(1)
            start_num = int(match.group(2)) + 1
        else:
            root = base
            start_num = 2

        candidate_num = start_num
        while True:
            candidate = f"{root} ({candidate_num}){ext}"
            if not os.path.exists(candidate):
                return candidate
            candidate_num += 1

    def _resolve_duplicate_output_template(
        self,
        yt_dlp_path: str,
        url: str,
        output_template: Optional[str],
        output_dir: str,
        on_log: Callable[[str], None]
    ) -> Optional[str]:
        """
        Resolve output path for duplicate mode by precomputing filename and applying (2) suffix if needed.

        Args:
            yt_dlp_path: Path to yt-dlp executable
            url: Media URL
            output_template: Current output template
            output_dir: Output directory
            on_log: Logging callback

        Returns:
            Unique output path template (fixed path) or None if resolution fails
        """
        try:
            template = output_template or os.path.join(output_dir, "%(title)s.%(ext)s")
            probe_cmd = [
                yt_dlp_path,
                "--get-filename",
                "--no-playlist",
                "-o", template,
                url
            ]

            process = subprocess.Popen(
                probe_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            stdout, _ = process.communicate(timeout=30)

            if process.returncode != 0:
                return None

            predicted_path = (stdout or "").strip().splitlines()
            if not predicted_path:
                return None

            predicted = predicted_path[-1].strip()
            if not predicted:
                return None

            unique_path = self._get_unique_filepath(predicted)
            return unique_path

        except Exception:
            return None

    @staticmethod
    def _normalize_audio_quality(value: Optional[str]) -> str:
        """Normalize audio quality/bitrate value for yt-dlp --audio-quality."""
        if value is None:
            return "0"
        text = str(value).strip().lower()
        if not text or text in ("best", "auto"):
            return "0"
        if text in ("worst", "low"):
            return "9"
        if text.endswith("k"):
            text = text[:-1]
        return text

    def _embed_thumbnail(self, input_file: str, thumbnail_file: str, on_log, ffmpeg_path: Optional[str] = None) -> bool:
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
                on_log(f"⚠ Thumbnail file not found, skipping embedding")
                return True

            base, ext = os.path.splitext(input_file)
            ext_lower = ext.lower()
            output_file = f"{base}_with_thumb{ext}"

            # Use mutagen for container-native artwork in formats where ffmpeg attached_pic is unreliable.
            if ext_lower in ['.flac', '.opus', '.ogg']:
                return self._embed_thumbnail_with_mutagen(input_file, thumbnail_file, on_log)

            # Determine appropriate codec and settings based on audio format
            ffmpeg_cmd = ffmpeg_path or "ffmpeg"

            if ext_lower in ['.mp3', '.aac', '.m4a']:
                # For MP3/AAC/M4A, use mjpeg codec for thumbnail
                cmd = [
                    ffmpeg_cmd, "-y",
                    "-i", input_file,
                    "-i", thumbnail_file,
                    "-c", "copy",
                    "-map", "0",
                    "-map", "1",
                    "-c:v", "mjpeg",
                    "-disposition:v", "attached_pic",
                    output_file
                ]
            elif ext_lower in ['.wav']:
                # For WAV, we need to convert thumbnail to appropriate format
                # WAV doesn't support embedded thumbnails in standard way, so we'll skip
                on_log(f"⚠ WAV format doesn't support embedded thumbnails in standard way")
                return True
            else:
                # Default command for other formats
                cmd = [
                    ffmpeg_cmd, "-y",
                    "-i", input_file,
                    "-i", thumbnail_file,
                    "-map", "0",
                    "-map", "1",
                    "-c", "copy",
                    "-c:v", "mjpeg" if ext_lower == '.mp3' else "copy",
                    "-disposition:v", "attached_pic",
                    output_file
                ]

            on_log(f"Embedding thumbnail...")

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
                if line and ("frame=" in line or "Stream mapping:" in line):
                    on_log(line)

            process.wait()

            if process.returncode == 0:
                # Replace original file with thumbnail-embedded version
                if os.path.exists(input_file):
                    os.remove(input_file)
                os.rename(output_file, input_file)
                on_log(f"✓ Thumbnail embedded successfully")
                return True
            else:
                on_log(f"⚠ Failed to embed thumbnail (code: {process.returncode})")
                # Clean up failed output file if it exists
                if os.path.exists(output_file):
                    os.remove(output_file)
                return False

        except Exception as e:
            on_log(f"⚠ Thumbnail embedding error: {str(e)}")
            return False

    def _embed_thumbnail_video(self, input_file: str, thumbnail_file: str, on_log, ffmpeg_path: Optional[str] = None) -> bool:
        """
        Embed thumbnail into a video container as an attached picture stream.

        Args:
            input_file: Path to video file
            thumbnail_file: Path to thumbnail image
            on_log: Logging callback
            ffmpeg_path: Optional path to ffmpeg executable

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(thumbnail_file):
                on_log("⚠ Thumbnail file not found, skipping embedding")
                return True

            base, ext = os.path.splitext(input_file)
            output_file = f"{base}_with_thumb{ext}"
            ffmpeg_cmd = ffmpeg_path or "ffmpeg"

            # Attach thumbnail without re-encoding the main video stream
            cmd = [
                ffmpeg_cmd, "-y",
                "-i", input_file,
                "-i", thumbnail_file,
                "-map", "0",
                "-map", "1",
                "-c", "copy",
                "-c:v:1", "mjpeg",
                "-disposition:v:1", "attached_pic",
                output_file
            ]

            on_log("Embedding thumbnail into video...")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            for line in process.stderr:
                line = line.rstrip()
                if line and ("frame=" in line or "Stream mapping:" in line):
                    on_log(line)

            process.wait()

            if process.returncode == 0:
                if os.path.exists(input_file):
                    os.remove(input_file)
                os.rename(output_file, input_file)
                on_log("✓ Thumbnail embedded successfully (video)")
                return True

            on_log(f"⚠ Failed to embed thumbnail (code: {process.returncode})")
            if os.path.exists(output_file):
                os.remove(output_file)
            return False

        except Exception as e:
            on_log(f"⚠ Thumbnail embedding error: {str(e)}")
            return False

    def _embed_thumbnail_with_mutagen(self, input_file: str, thumbnail_file: str, on_log) -> bool:
        """
        Embed artwork using mutagen metadata blocks (works for FLAC/OPUS/OGG).

        Args:
            input_file: Path to target audio file
            thumbnail_file: Path to image file
            on_log: Logging callback

        Returns:
            True if successful, False otherwise
        """
        try:
            from mutagen.flac import FLAC, Picture
            from mutagen.oggopus import OggOpus
            from mutagen.oggvorbis import OggVorbis
        except Exception:
            on_log("⚠ mutagen is not available in this Python environment")
            return False

        try:
            _, ext = os.path.splitext(input_file)
            ext_lower = ext.lower()
            with open(thumbnail_file, "rb") as f:
                image_data = f.read()

            thumb_ext = os.path.splitext(thumbnail_file)[1].lower()
            if thumb_ext in ['.jpg', '.jpeg']:
                mime = "image/jpeg"
            elif thumb_ext == '.png':
                mime = "image/png"
            elif thumb_ext == '.webp':
                mime = "image/webp"
            else:
                mime = "image/jpeg"

            picture = Picture()
            picture.data = image_data
            picture.type = 3  # Front cover
            picture.mime = mime
            picture.desc = "Cover"

            if ext_lower == '.flac':
                audio = FLAC(input_file)
                try:
                    audio.clear_pictures()
                except Exception:
                    pass
                audio.add_picture(picture)
                audio.save()
                on_log("✓ Thumbnail embedded successfully (mutagen/flac)")
                return True

            if ext_lower == '.opus':
                audio = OggOpus(input_file)
                pic_b64 = base64.b64encode(picture.write()).decode("ascii")
                try:
                    del audio["metadata_block_picture"]
                except Exception:
                    pass
                audio["metadata_block_picture"] = [pic_b64]
                audio.save()
                on_log("✓ Thumbnail embedded successfully (mutagen/opus)")
                return True

            if ext_lower == '.ogg':
                audio = OggVorbis(input_file)
                pic_b64 = base64.b64encode(picture.write()).decode("ascii")
                try:
                    del audio["metadata_block_picture"]
                except Exception:
                    pass
                audio["metadata_block_picture"] = [pic_b64]
                audio.save()
                on_log("✓ Thumbnail embedded successfully (mutagen/ogg)")
                return True

            on_log(f"⚠ Unsupported format for mutagen embedding: {ext_lower}")
            return False

        except Exception as e:
            on_log(f"⚠ mutagen embed failed: {str(e)}")
            return False

    def _trim_with_ffmpeg(
        self,
        input_file: str,
        start_time: Optional[str],
        end_time: Optional[str],
        on_log: Callable[[str], None],
        output_dir: Optional[str] = None,
        keep_original_file: bool = False,
        save_thumbnail_file: bool = False,
        ffmpeg_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Trim video/audio file using FFmpeg, preserving thumbnails for audio files

        Args:
            input_file: Path to input file
            start_time: Start time (HH:MM:SS) or None
            end_time: End time (HH:MM:SS) or None
            on_log: Logging callback
            output_dir: Output directory (used to find thumbnail file)
            save_thumbnail_file: Whether to keep thumbnail file after embedding
            ffmpeg_path: Optional path to ffmpeg executable

        Returns:
            Path to processed file if successful, None otherwise
        """
        try:
            # Check if this is an audio file (needs thumbnail embedding)
            base, ext = os.path.splitext(input_file)
            ext_lower = ext.lower()
            
            # Define which formats support embedded thumbnails
            audio_formats_with_thumbnails = ['.mp3', '.aac', '.m4a', '.flac', '.opus', '.ogg']
            is_audio_with_thumbnail_support = ext_lower in audio_formats_with_thumbnails

            # Find thumbnail file downloaded by yt-dlp (if trimming was enabled)
            thumbnail_file = None
            if output_dir:
                thumbnail_file = self._find_thumbnail_file(input_file, output_dir)
                if thumbnail_file:
                    on_log(f"Found thumbnail: {os.path.basename(thumbnail_file)}")

            # Create output filename
            output_file = f"{base}_trimmed{ext}"

            # Build FFmpeg command for trimming
            ffmpeg_cmd = ffmpeg_path or "ffmpeg"
            cmd = [ffmpeg_cmd, "-y", "-i", input_file]

            # Add start time if specified (after input for accurate seeking)
            if start_time and start_time != "00:00:00":
                cmd.extend(["-ss", start_time])

            # Add end time if specified
            if end_time and end_time != "00:00:00":
                cmd.extend(["-to", end_time])

            # For audio files that support thumbnails, we need to be careful to preserve metadata
            if is_audio_with_thumbnail_support:
                cmd.extend([
                    "-c", "copy",
                    "-map_metadata", "0",
                    "-map", "0",
                    "-avoid_negative_ts", "make_zero",
                    output_file
                ])
            else:
                # For video or audio without thumbnail support
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
                # Replace original or keep side-by-side based on option
                if keep_original_file:
                    processed_file = output_file
                    on_log(f"✓ File trimmed: {os.path.basename(processed_file)}")
                else:
                    os.remove(input_file)
                    os.rename(output_file, input_file)
                    processed_file = input_file
                    on_log(f"✓ File trimmed: {os.path.basename(processed_file)}")

                # Re-embed thumbnail if present
                if thumbnail_file:
                    if is_audio_with_thumbnail_support:
                        success = self._embed_thumbnail(processed_file, thumbnail_file, on_log, ffmpeg_path=ffmpeg_path)
                    else:
                        success = self._embed_thumbnail_video(processed_file, thumbnail_file, on_log, ffmpeg_path=ffmpeg_path)
                    if not success:
                        on_log("⚠ Could not embed thumbnail, but file was trimmed successfully")

                    if not save_thumbnail_file:
                        try:
                            if os.path.exists(thumbnail_file):
                                os.remove(thumbnail_file)
                        except Exception as e:
                            on_log(f"⚠ Could not clean up thumbnail file: {str(e)}")
                elif is_audio_with_thumbnail_support:
                    on_log("⚠ No thumbnail found to embed")

                return processed_file
            else:
                on_log(f"✗ FFmpeg failed with code: {process.returncode}")
                # Clean up failed output file if it exists
                if os.path.exists(output_file):
                    os.remove(output_file)
                # Clean up thumbnail file if extraction was done
                if thumbnail_file and os.path.exists(thumbnail_file) and not save_thumbnail_file:
                    try:
                        os.remove(thumbnail_file)
                    except Exception as e:
                        on_log(f"⚠ Could not clean up thumbnail file: {str(e)}")
                return None

        except FileNotFoundError:
            on_log("✗ FFmpeg not found. Please install FFmpeg and add it to PATH")
            on_log("  Download from: https://ffmpeg.org/download.html")
            return None
        except Exception as e:
            on_log(f"✗ Trim error: {str(e)}")
            return None

    def _convert_with_ffmpeg(
        self,
        input_file: str,
        target_format: str,
        on_log: Callable[[str], None],
        output_dir: Optional[str] = None,
        keep_original_file: bool = False,
        save_thumbnail_file: bool = False,
        ffmpeg_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Convert video/audio file to target format using FFmpeg

        Args:
            input_file: Path to input file
            target_format: Target format (e.g., 'mp4', 'mkv', 'mp3', etc.)
            on_log: Logging callback
            output_dir: Output directory (used to find thumbnail file)
            save_thumbnail_file: Whether to keep thumbnail file after embedding
            ffmpeg_path: Optional path to ffmpeg executable

        Returns:
            Path to converted file if successful, None otherwise
        """
        try:
            base, ext = os.path.splitext(input_file)
            ext_lower = ext.lower().lstrip('.')
            target_format_lower = target_format.lower()

            # Find thumbnail file if available
            thumbnail_file = None
            if output_dir:
                thumbnail_file = self._find_thumbnail_file(input_file, output_dir)
                if thumbnail_file:
                    on_log(f"Found thumbnail: {os.path.basename(thumbnail_file)}")

            # Skip conversion if already in target format
            if ext_lower == target_format_lower:
                on_log(f"File already in {target_format} format, skipping conversion")
                audio_formats_with_thumbnails = ['mp3', 'aac', 'm4a', 'flac', 'opus', 'ogg']
                if target_format_lower in audio_formats_with_thumbnails and thumbnail_file:
                    success = self._embed_thumbnail(input_file, thumbnail_file, on_log, ffmpeg_path=ffmpeg_path)
                    if not success:
                        on_log("⚠ Could not embed thumbnail, but file was not converted")
                if thumbnail_file and os.path.exists(thumbnail_file) and not save_thumbnail_file:
                    try:
                        os.remove(thumbnail_file)
                    except Exception as e:
                        on_log(f"⚠ Could not clean up thumbnail file: {str(e)}")
                return input_file

            # Define format categories
            audio_formats = ['mp3', 'wav', 'aac', 'm4a', 'opus', 'vorbis', 'flac', 'ogg']
            video_formats = ['mp4', 'mkv', 'avi', 'mov', 'webm', 'flv']

            is_gif_target = target_format_lower == 'gif'
            is_audio_target = target_format_lower in audio_formats
            is_video_target = target_format_lower in video_formats

            # Create output filename
            output_file = f"{base}.{target_format_lower}"

            # Build FFmpeg command based on target format
            ffmpeg_cmd = ffmpeg_path or "ffmpeg"
            cmd = [ffmpeg_cmd, "-y", "-i", input_file]

            if is_gif_target:
                palette_file = f"{base}_palette.png"
                output_file = f"{base}.gif"

                gif_fps = "15"
                gif_scale = "480:-1:flags=lanczos"

                palette_cmd = [
                    ffmpeg_cmd, "-y",
                    "-i", input_file,
                    "-vf", f"fps={gif_fps},scale={gif_scale},palettegen=stats_mode=diff",
                    palette_file
                ]

                on_log("Generating GIF palette...")
                on_log(f"Command: {' '.join(palette_cmd)}")

                process = subprocess.Popen(
                    palette_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding='utf-8',
                    errors='replace',
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )

                for line in process.stderr:
                    line = line.rstrip()
                    if line and any(x in line for x in ['frame=', 'time=', 'Stream', 'Output', 'Error', 'error']):
                        on_log(line)

                process.wait()

                if process.returncode != 0:
                    on_log(f"✗ FFmpeg palette generation failed with code: {process.returncode}")
                    if os.path.exists(palette_file):
                        os.remove(palette_file)
                    return None

                gif_cmd = [
                    ffmpeg_cmd, "-y",
                    "-i", input_file,
                    "-i", palette_file,
                    "-lavfi", f"fps={gif_fps},scale={gif_scale}[x];[x][1:v]paletteuse",
                    "-loop", "0",
                    output_file
                ]

                on_log(f"Converting to {target_format_lower} with FFmpeg...")
                on_log(f"Command: {' '.join(gif_cmd)}")

                process = subprocess.Popen(
                    gif_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding='utf-8',
                    errors='replace',
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )

                for line in process.stderr:
                    line = line.rstrip()
                    if line and any(x in line for x in ['frame=', 'time=', 'Stream', 'Output', 'Error', 'error']):
                        on_log(line)

                process.wait()

                # Clean up palette file
                if os.path.exists(palette_file):
                    try:
                        os.remove(palette_file)
                    except Exception as e:
                        on_log(f"⚠ Could not remove palette file: {str(e)}")

                if process.returncode != 0:
                    on_log(f"✗ FFmpeg conversion failed with code: {process.returncode}")
                    if os.path.exists(output_file):
                        os.remove(output_file)
                    return None

                on_log(f"✓ Converted to {target_format_lower}: {os.path.basename(output_file)}")

                # Remove original file unless user wants to keep it
                if not keep_original_file:
                    try:
                        os.remove(input_file)
                    except Exception as e:
                        on_log(f"⚠ Could not remove original file: {str(e)}")

                # Clean up thumbnail file if present
                if thumbnail_file and os.path.exists(thumbnail_file) and not save_thumbnail_file:
                    try:
                        os.remove(thumbnail_file)
                    except Exception as e:
                        on_log(f"⚠ Could not clean up thumbnail file: {str(e)}")

                return output_file

            if is_audio_target:
                # Audio conversion
                codec_map = {
                    'mp3': ['-c:a', 'libmp3lame', '-q:a', '0'],
                    'aac': ['-c:a', 'aac', '-b:a', '192k'],
                    'm4a': ['-c:a', 'aac', '-b:a', '192k'],
                    'opus': ['-c:a', 'libopus', '-b:a', '128k'],
                    'vorbis': ['-c:a', 'libvorbis', '-q:a', '6'],
                    'ogg': ['-c:a', 'libvorbis', '-q:a', '6'],
                    'flac': ['-c:a', 'flac'],
                    'wav': ['-c:a', 'pcm_s16le'],
                }
                codec_args = codec_map.get(target_format_lower, ['-c:a', 'copy'])
                cmd.extend(codec_args)
                cmd.extend(['-vn'])  # No video for audio-only output
                cmd.append(output_file)

            elif is_video_target:
                # Video conversion - use copy where possible for speed
                codec_map = {
                    'mp4': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-c:a', 'aac', '-b:a', '192k'],
                    'mkv': ['-c:v', 'copy', '-c:a', 'copy'],  # MKV is a container, usually can copy
                    'webm': ['-c:v', 'libvpx-vp9', '-crf', '30', '-b:v', '0', '-c:a', 'libopus', '-b:a', '128k'],
                    'avi': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-c:a', 'mp3', '-b:a', '192k'],
                    'mov': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-c:a', 'aac', '-b:a', '192k'],
                    'flv': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-c:a', 'aac', '-b:a', '128k'],
                }
                codec_args = codec_map.get(target_format_lower, ['-c:v', 'copy', '-c:a', 'copy'])

                # For MKV, try to copy streams first (fast), re-encode only if needed
                if target_format_lower == 'mkv':
                    cmd.extend(['-c', 'copy'])
                else:
                    cmd.extend(codec_args)

                cmd.extend(['-map_metadata', '0'])
                cmd.append(output_file)
            else:
                on_log(f"⚠ Unknown target format: {target_format}")
                return None

            on_log(f"Converting to {target_format_lower} with FFmpeg...")
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
                    # Only log important lines to avoid spam
                    if any(x in line for x in ['frame=', 'time=', 'Stream', 'Output', 'Error', 'error']):
                        on_log(line)

            process.wait()

            if process.returncode == 0:
                on_log(f"✓ Converted to {target_format_lower}: {os.path.basename(output_file)}")

                # Remove original file unless user wants to keep it
                if not keep_original_file:
                    try:
                        os.remove(input_file)
                    except Exception as e:
                        on_log(f"⚠ Could not remove original file: {str(e)}")

                # Embed thumbnail for audio formats that support artwork metadata blocks
                audio_formats_with_thumbnails = ['mp3', 'aac', 'm4a', 'flac', 'opus', 'ogg']
                if target_format_lower in audio_formats_with_thumbnails and thumbnail_file:
                    success = self._embed_thumbnail(output_file, thumbnail_file, on_log, ffmpeg_path=ffmpeg_path)
                    if not success:
                        on_log("⚠ Could not embed thumbnail, but conversion was successful")

                # Clean up thumbnail file
                if thumbnail_file and os.path.exists(thumbnail_file) and not save_thumbnail_file:
                    try:
                        os.remove(thumbnail_file)
                    except Exception as e:
                        on_log(f"⚠ Could not clean up thumbnail file: {str(e)}")

                return output_file
            else:
                on_log(f"✗ FFmpeg conversion failed with code: {process.returncode}")
                # Clean up failed output file if it exists
                if os.path.exists(output_file):
                    os.remove(output_file)
                return None

        except FileNotFoundError:
            on_log("✗ FFmpeg not found. Please install FFmpeg and add it to PATH")
            on_log("  Download from: https://ffmpeg.org/download.html")
            return None
        except Exception as e:
            on_log(f"✗ Conversion error: {str(e)}")
            return None
