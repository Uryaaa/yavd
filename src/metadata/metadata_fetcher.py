"""Metadata fetcher for video information"""

import subprocess
import json
import threading
import os
from typing import Callable, Optional, Dict, Any


class MetadataFetcher:
    """Fetches video metadata using yt-dlp"""
    
    def __init__(self):
        """Initialize metadata fetcher"""
        self.is_fetching = False
    
    def fetch_metadata(
        self,
        yt_dlp_path: str,
        url: str,
        on_success: Callable[[Dict[str, Any]], None],
        on_error: Callable[[str], None]
    ):
        """
        Fetch video metadata in a separate thread
        
        Args:
            yt_dlp_path: Path to yt-dlp executable
            url: Video URL to fetch metadata for
            on_success: Callback function with metadata dict
            on_error: Callback function when fetch fails
        """
        if self.is_fetching:
            on_error("Metadata fetch already in progress")
            return
        
        # Start fetch in separate thread
        thread = threading.Thread(
            target=self._fetch_thread,
            args=(yt_dlp_path, url, on_success, on_error),
            daemon=True
        )
        thread.start()
    
    def _fetch_thread(
        self,
        yt_dlp_path: str,
        url: str,
        on_success: Callable[[Dict[str, Any]], None],
        on_error: Callable[[str], None]
    ):
        """
        Execute metadata fetch in background thread
        
        Args:
            yt_dlp_path: Path to yt-dlp executable
            url: Video URL to fetch metadata for
            on_success: Callback function with metadata dict
            on_error: Callback function when fetch fails
        """
        self.is_fetching = True
        
        try:
            # Build command to get JSON metadata
            cmd = [
                yt_dlp_path,
                "--dump-json",
                "--no-playlist",
                "--skip-download",
                url
            ]
            
            # Execute command and capture output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            stdout, stderr = process.communicate(timeout=30)
            
            if process.returncode == 0:
                # Parse JSON metadata
                metadata = json.loads(stdout)

                # Extract and process formats
                formats_data = self._process_formats(metadata.get('formats', []))

                # Extract relevant information
                video_info = {
                    'title': metadata.get('title', 'Unknown'),
                    'duration': metadata.get('duration', 0),
                    'uploader': metadata.get('uploader', 'Unknown'),
                    'upload_date': metadata.get('upload_date', ''),
                    'view_count': metadata.get('view_count', 0),
                    'thumbnail': metadata.get('thumbnail', ''),
                    'description': metadata.get('description', ''),
                    'formats': metadata.get('formats', []),
                    'width': metadata.get('width', 0),
                    'height': metadata.get('height', 0),
                    'available_resolutions': formats_data['resolutions'],
                    'available_formats': formats_data['formats'],
                    'available_framerates': formats_data['framerates'],
                    'available_audio_bitrates': formats_data['audio_bitrates'],
                    'format_details': formats_data['details'],
                }

                on_success(video_info)
            else:
                on_error(f"Failed to fetch metadata: {stderr}")
        
        except subprocess.TimeoutExpired:
            on_error("Metadata fetch timed out (30 seconds)")
        except json.JSONDecodeError as e:
            on_error(f"Failed to parse metadata: {str(e)}")
        except Exception as e:
            on_error(f"Error fetching metadata: {str(e)}")
        
        finally:
            self.is_fetching = False
    
    @staticmethod
    def _process_formats(formats: list) -> dict:
        """
        Process available formats from yt-dlp metadata

        Args:
            formats: List of format dictionaries from yt-dlp

        Returns:
            Dictionary with keys: 'resolutions', 'formats', 'framerates', 'audio_bitrates', 'quality_options', 'details'
        """
        resolutions = set()
        format_extensions = set()
        framerates = set()
        audio_bitrates = set()
        quality_options = {}  # Maps "resolution fps" to format_id
        details = []

        for fmt in formats:
            # Get resolution
            height = fmt.get('height')
            width = fmt.get('width')
            fps = fmt.get('fps')

            # Get format/extension
            ext = fmt.get('ext', '')
            if ext:
                format_extensions.add(ext.upper())

            # Get audio bitrate
            abr = fmt.get('abr')  # Audio bitrate
            if abr and abr > 0:
                audio_bitrates.add(f"{int(abr)}k")

            # Build quality option key (resolution + fps)
            if height and height > 0:
                resolutions.add(f"{height}p")
                if fps and fps > 0:
                    framerates.add(f"{int(fps)}fps")
                    quality_key = f"{height}p {int(fps)}fps"
                else:
                    quality_key = f"{height}p"

                # Store format_id for this quality option
                format_id = fmt.get('format_id', '')
                if format_id and quality_key not in quality_options:
                    quality_options[quality_key] = format_id

            # Store detailed format info
            format_info = {
                'format_id': fmt.get('format_id', ''),
                'ext': ext,
                'height': height,
                'width': width,
                'fps': fps,
                'vcodec': fmt.get('vcodec', 'unknown'),
                'acodec': fmt.get('acodec', 'unknown'),
                'abr': abr,  # Audio bitrate
                'tbr': fmt.get('tbr'),  # Total bitrate
                'filesize': fmt.get('filesize'),
                'format': fmt.get('format', ''),
                'has_video': height is not None and height > 0,
                'has_audio': fmt.get('acodec', 'none') != 'none',
            }
            details.append(format_info)

        # Sort resolutions numerically
        sorted_resolutions = sorted(
            list(resolutions),
            key=lambda x: int(x.rstrip('p')),
            reverse=True
        )

        # Sort framerates numerically
        sorted_framerates = sorted(
            list(framerates),
            key=lambda x: int(x.rstrip('fps')),
            reverse=True
        )

        # Sort audio bitrates numerically
        sorted_audio_bitrates = sorted(
            list(audio_bitrates),
            key=lambda x: int(x.rstrip('k')),
            reverse=True
        )

        return {
            'resolutions': sorted_resolutions,
            'formats': sorted(list(format_extensions)),
            'framerates': sorted_framerates,
            'audio_bitrates': sorted_audio_bitrates,
            'quality_options': quality_options,
            'details': details,
        }

    @staticmethod
    def format_duration(seconds: int) -> str:
        """
        Format duration in seconds to HH:MM:SS
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted duration string
        """
        if seconds <= 0:
            return "00:00:00"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    @staticmethod
    def format_number(num: int) -> str:
        """
        Format large numbers with commas
        
        Args:
            num: Number to format
            
        Returns:
            Formatted number string
        """
        return f"{num:,}"

