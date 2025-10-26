"""Metadata fetcher for video information"""

import subprocess
import json
import threading
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
                errors='replace'
            )
            
            stdout, stderr = process.communicate(timeout=30)
            
            if process.returncode == 0:
                # Parse JSON metadata
                metadata = json.loads(stdout)
                
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

