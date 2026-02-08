"""Main application window"""

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import os
from pathlib import Path
from io import BytesIO
import urllib.request
import re
from urllib.parse import urlparse

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from ..config import ConfigManager
from ..downloader import Downloader
from ..metadata import MetadataFetcher
from ..ytdlp_manager import YtdlpDownloader
from ..ffmpeg_manager import FFmpegDownloader
from ..templates import TemplateManager
from .playlist_selector import PlaylistSelector
from .main_window_ui import MainWindowUI
from .main_window_tools import MainWindowTools


class MainWindow(MainWindowUI, MainWindowTools):
    """Main GUI window for yt-dlp downloader"""
    
    def __init__(self, root):
        """
        Initialize main window

        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title("YAVDownloader - Yet Another Video Downloader")
        self.root.geometry("750x600")
        self.root.minsize(650, 600)
        self.root.resizable(True, True)

        # Set window icon
        try:
            icon_path = Path(__file__).parent.parent.parent / "icon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except:
            pass  # Ignore if icon not found

        # Configure modern styling
        self._configure_styles()
        
        # Initialize config manager
        self.config = ConfigManager()

        # Initialize downloader
        self.downloader = Downloader()

        # Initialize metadata fetcher
        self.metadata_fetcher = MetadataFetcher()

        # Initialize yt-dlp manager
        self.ytdlp_downloader = YtdlpDownloader()

        # Initialize FFmpeg manager
        self.ffmpeg_downloader = FFmpegDownloader()

        # Initialize template manager
        self.template_manager = TemplateManager()

        # Store current video metadata
        self.current_metadata = None

        # Store current template command (if using template)
        self.current_template_command = None

        # Track if metadata has been fetched
        self.metadata_fetched = False
        self.last_url_value = ""

        # Template mode state
        self.template_active = False

        # Playlist caching - avoid re-fetching same playlist
        self.cached_playlist_url = ''
        self.cached_playlist_data = None
        self.selected_video_ids = set()  # Preserve selections when re-opening

        # Install Tk error handler to suppress CTk widget resize errors
        # (CTkRadioButton/CTkCheckBox inside CTkScrollableFrame can crash during rapid resize)
        self._original_tk_report_callback_exception = self.root.report_callback_exception
        self.root.report_callback_exception = self._handle_tk_error

        # Create UI
        self.create_widgets()

        # Load saved settings
        self._load_user_settings()
        self._bind_setting_savers()

        # Load saved yt-dlp path
        saved_path = self.config.get('yt_dlp_path', '')
        if saved_path:
            self.yt_dlp_entry.insert(0, saved_path)

    def _set_section_state(self, frame, state: str):
        """Enable/disable all interactive widgets inside a frame."""
        try:
            children = frame.winfo_children()
        except Exception:
            return

        for child in children:
            try:
                if isinstance(child, (ctk.CTkFrame, tk.Frame)):
                    self._set_section_state(child, state)
                else:
                    child.configure(state=state)
            except Exception:
                pass

    def _set_template_mode(self, active: bool, template_name: str = ""):
        """Toggle template mode UI and lock conflicting controls."""
        self.template_active = active

        if active:
            label_text = f"Template active: {template_name} — download settings locked"
            self.template_mode_label.configure(text=label_text)
            self.template_mode_frame.grid()
            # Lock sections that conflict with template command
            if hasattr(self, "mode_frame"):
                self._set_section_state(self.mode_frame, "disabled")
            if hasattr(self, "format_frame"):
                self._set_section_state(self.format_frame, "disabled")
            self._set_section_state(self.quality_label_frame, "disabled")
            self._set_section_state(self.convert_frame, "disabled")
            self._set_section_state(self.trim_frame, "disabled")
            if hasattr(self, "other_options_frame"):
                self._set_section_state(self.other_options_frame, "disabled")
            if hasattr(self, "sponsorblock_tab"):
                self._set_section_state(self.sponsorblock_tab, "disabled")
        else:
            self.template_mode_frame.grid_remove()
            if hasattr(self, "mode_frame"):
                self._set_section_state(self.mode_frame, "normal")
            if hasattr(self, "format_frame"):
                self._set_section_state(self.format_frame, "normal")
            self._set_section_state(self.quality_label_frame, "normal")
            self._set_section_state(self.convert_frame, "normal")
            self._set_section_state(self.trim_frame, "normal")
            if hasattr(self, "other_options_frame"):
                self._set_section_state(self.other_options_frame, "normal")
            if hasattr(self, "sponsorblock_tab"):
                self._set_section_state(self.sponsorblock_tab, "normal")
                if hasattr(self, "_toggle_sponsorblock_controls"):
                    self._toggle_sponsorblock_controls()

    def _clear_template_mode(self):
        """Clear active template and unlock download settings."""
        self.current_template_command = None
        self._set_template_mode(False)


    def _load_user_settings(self):
        """Load user settings from config and apply to UI."""
        # Output directory
        saved_output = self.config.get('output_dir', '')
        if saved_output:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, saved_output)

        # Mode/format/quality
        saved_mode = self.config.get('mode', '')
        if saved_mode and hasattr(self, 'mode_var'):
            if saved_mode == "auto":
                saved_mode = "video_audio"
            self.mode_var.set(saved_mode)

        saved_format = self.config.get('format', '')
        if saved_format and hasattr(self, 'format_var'):
            self.format_var.set(saved_format)

        saved_quality = self.config.get('quality', '')
        if saved_quality and hasattr(self, 'quality_var'):
            self.quality_var.set(saved_quality)

        saved_audio_bitrate = self.config.get('audio_bitrate', '')
        if saved_audio_bitrate and hasattr(self, 'audio_bitrate_var'):
            self.audio_bitrate_var.set(saved_audio_bitrate)

        # Convert settings
        if hasattr(self, 'convert_enabled'):
            self.convert_enabled.set(bool(self.config.get('convert_enabled', False)))
        saved_convert_format = self.config.get('convert_format', '')
        if saved_convert_format and hasattr(self, 'convert_format_var'):
            self.convert_format_var.set(saved_convert_format)

        # Trim settings
        if hasattr(self, 'trim_enabled'):
            self.trim_enabled.set(bool(self.config.get('trim_enabled', False)))
        saved_trim_start = self.config.get('trim_start', '')
        if saved_trim_start:
            self.trim_start_entry.delete(0, tk.END)
            self.trim_start_entry.insert(0, saved_trim_start)
        saved_trim_end = self.config.get('trim_end', '')
        if saved_trim_end:
            self.trim_end_entry.delete(0, tk.END)
            self.trim_end_entry.insert(0, saved_trim_end)

        # Save location for yt-dlp/ffmpeg download tabs
        saved_ytdlp_save = self.config.get('ytdlp_save_path', '')
        if saved_ytdlp_save and hasattr(self, 'ytdlp_save_entry'):
            self.ytdlp_save_entry.delete(0, tk.END)
            self.ytdlp_save_entry.insert(0, saved_ytdlp_save)

        saved_ffmpeg_save = self.config.get('ffmpeg_save_path', '')
        if saved_ffmpeg_save and hasattr(self, 'ffmpeg_save_entry'):
            self.ffmpeg_save_entry.delete(0, tk.END)
            self.ffmpeg_save_entry.insert(0, saved_ffmpeg_save)

        # Apply UI state changes after loading
        try:
            self._on_mode_changed()
            self._toggle_convert_controls()
            self._toggle_trim_controls()
        except Exception:
            pass

    def _bind_setting_savers(self):
        """Bind UI changes to persist settings."""
        def save_output_dir(_event=None):
            self.config.set('output_dir', self.output_entry.get().strip())

        self.output_entry.bind("<FocusOut>", save_output_dir)
        self.output_entry.bind("<Return>", save_output_dir)

        if hasattr(self, 'mode_var'):
            self.mode_var.trace_add("write", lambda *_: self.config.set('mode', self.mode_var.get()))
        if hasattr(self, 'format_var'):
            self.format_var.trace_add("write", lambda *_: self.config.set('format', self.format_var.get()))
        if hasattr(self, 'quality_var'):
            self.quality_var.trace_add("write", lambda *_: self.config.set('quality', self.quality_var.get()))
        if hasattr(self, 'audio_bitrate_var'):
            self.audio_bitrate_var.trace_add("write", lambda *_: self.config.set('audio_bitrate', self.audio_bitrate_var.get()))
        if hasattr(self, 'convert_enabled'):
            self.convert_enabled.trace_add("write", lambda *_: self.config.set('convert_enabled', bool(self.convert_enabled.get())))
        if hasattr(self, 'convert_format_var'):
            self.convert_format_var.trace_add("write", lambda *_: self.config.set('convert_format', self.convert_format_var.get()))
        if hasattr(self, 'trim_enabled'):
            self.trim_enabled.trace_add("write", lambda *_: self.config.set('trim_enabled', bool(self.trim_enabled.get())))

        def save_trim_times(_event=None):
            self.config.set('trim_start', self.trim_start_entry.get())
            self.config.set('trim_end', self.trim_end_entry.get())

        self.trim_start_entry.bind("<FocusOut>", save_trim_times)
        self.trim_end_entry.bind("<FocusOut>", save_trim_times)

        def save_ytdlp_save(_event=None):
            if hasattr(self, 'ytdlp_save_entry'):
                self.config.set('ytdlp_save_path', self.ytdlp_save_entry.get().strip())

        if hasattr(self, 'ytdlp_save_entry'):
            self.ytdlp_save_entry.bind("<FocusOut>", save_ytdlp_save)
            self.ytdlp_save_entry.bind("<Return>", save_ytdlp_save)

        def save_ffmpeg_save(_event=None):
            if hasattr(self, 'ffmpeg_save_entry'):
                self.config.set('ffmpeg_save_path', self.ffmpeg_save_entry.get().strip())

        if hasattr(self, 'ffmpeg_save_entry'):
            self.ffmpeg_save_entry.bind("<FocusOut>", save_ffmpeg_save)
            self.ffmpeg_save_entry.bind("<Return>", save_ffmpeg_save)

    def _handle_tk_error(self, exc_type, exc_value, exc_tb):
        """Handle Tk callback exceptions, suppressing known CTk resize errors."""
        import traceback
        if exc_type is tk.TclError:
            msg = str(exc_value)
            if "invalid command name" in msg and ("ctkcanvas" in msg or "ctkradiobutton" in msg
                                                   or "ctkcheckbox" in msg):
                return  # Suppress known CTk widget resize errors
        # For all other errors, use the original handler
        self._original_tk_report_callback_exception(exc_type, exc_value, exc_tb)

    def browse_yt_dlp(self):
        """Browse for yt-dlp executable"""
        filename = filedialog.askopenfilename(
            title="Select yt-dlp executable",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )
        if filename:
            self.yt_dlp_entry.delete(0, tk.END)
            self.yt_dlp_entry.insert(0, filename)
            self.config.set('yt_dlp_path', filename)
            self.log_message(f"yt-dlp path set to: {filename}")
    
    def browse_output(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, directory)
            self.config.set('output_dir', directory)

    def paste_url(self):
        """Paste URL from clipboard"""
        try:
            # Get text from clipboard
            clipboard_text = self.root.clipboard_get()
            # Clear current URL entry
            self.url_entry.delete(0, tk.END)
            # Insert clipboard text
            self.url_entry.insert(0, clipboard_text.strip())
            self.log_message(f"URL pasted from clipboard")
            # Trigger auto-fetch
            self._on_url_changed()
        except tk.TclError:
            # Clipboard is empty or contains non-text data
            messagebox.showwarning("Paste Error", "Clipboard is empty or contains invalid data")

    def fetch_video_info(self):
        """Fetch video metadata"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Please enter a video URL first")
            return

        yt_dlp_path = self.yt_dlp_entry.get().strip()
        if not yt_dlp_path:
            messagebox.showwarning("No yt-dlp", "Please select yt-dlp executable first")
            return

        # Check if we have cached playlist data for this URL
        if (self.cached_playlist_url == url and
            self.cached_playlist_data is not None and
            self.cached_playlist_data.get('is_playlist', False)):
            # Use cached data - show playlist selector immediately
            self.log_message("Using cached playlist data...")
            self._handle_playlist_detected(self.cached_playlist_data, use_cache=True)
            return

        self.status_var.set("Fetching video information...")
        self.log_message("Fetching video metadata...")

        # Fetch metadata
        self.metadata_fetcher.fetch_metadata(
            yt_dlp_path=yt_dlp_path,
            url=url,
            on_success=self._on_metadata_success,
            on_error=self._on_metadata_error
        )

    def _on_metadata_success(self, metadata):
        """Handle successful metadata fetch"""
        self.current_metadata = metadata

        # Check if this is a playlist
        if metadata.get('is_playlist', False):
            # Cache playlist data for this URL
            url = self.url_entry.get().strip()
            self.cached_playlist_url = url
            self.cached_playlist_data = metadata
            # Reset selections for new playlist
            self.selected_video_ids = set()

            self._handle_playlist_detected(metadata)
            return

        # Update metadata display
        self.metadata_title.configure(text=metadata.get('title', 'Unknown'))
        self.metadata_duration.configure(
            text=MetadataFetcher.format_duration(metadata.get('duration', 0))
        )
        self.metadata_uploader.configure(text=metadata.get('uploader', 'Unknown'))
        self.metadata_views.configure(
            text=MetadataFetcher.format_number(metadata.get('view_count', 0))
        )

        # Load and display thumbnail
        thumbnail_url = metadata.get('thumbnail', '')
        if thumbnail_url:
            self._load_thumbnail(thumbnail_url)

        # Update format options based on available formats
        available_formats = metadata.get('available_formats', ['MP4', 'MP3'])
        self._update_format_options(available_formats)

        # Update quality options based on available resolutions and framerates
        available_resolutions = metadata.get('available_resolutions', [])
        available_framerates = metadata.get('available_framerates', [])

        if available_resolutions:
            # Build quality options with framerate info
            quality_displays = []
            quality_values = []

            # Add resolution + framerate combinations
            for res in available_resolutions:
                res_num = res.rstrip('p')
                quality_displays.append(f"{res}")
                quality_values.append(res_num)

                # Add framerate variants if available
                for fps in available_framerates:
                    quality_displays.append(f"{res} {fps}")
                    quality_values.append(f"{res_num}_{fps}")

            quality_displays.extend(['Best Quality', 'Worst (smallest)'])
            quality_values.extend(['best', 'worst'])
            self._update_quality_options(quality_displays, quality_values)

        # Update audio bitrate options
        available_audio_bitrates = metadata.get('available_audio_bitrates', [])
        if available_audio_bitrates:
            bitrate_displays = list(available_audio_bitrates) + ['Best', 'Worst']
            bitrate_values = [b.rstrip('k') for b in available_audio_bitrates] + ['best', 'worst']
            self._update_audio_bitrate_options(bitrate_displays, bitrate_values)

        # Show format and quality sections
        self.format_label_frame.grid()
        self.quality_label_frame.grid()
        if hasattr(self, "other_options_frame"):
            self.other_options_frame.grid()

        # Show metadata frame
        self.metadata_frame.grid()

        # Show trim frame
        self.trim_frame.grid()

        # Show convert frame and update options based on mode
        self.convert_frame.grid()
        self._update_convert_format_options()

        # Update end time in trim section to video duration
        duration_str = MetadataFetcher.format_duration(metadata.get('duration', 0))
        self.trim_end_entry.delete(0, tk.END)
        self.trim_end_entry.insert(0, duration_str)

        # Expand window to accommodate metadata
        self._resize_window_for_metadata()

        # Check if scrollbar is needed after showing metadata
        self.root.after(100, self._check_scrollbar_needed)

        # Enable download button now that metadata is fetched
        self.metadata_fetched = True
        self.download_btn.configure(state='normal')

        self.status_var.set("Video information fetched successfully")
        self.log_message(f"✓ Video: {metadata.get('title', 'Unknown')}")
        self.log_message(f"  Duration: {MetadataFetcher.format_duration(metadata.get('duration', 0))}")
        self.log_message(f"  Uploader: {metadata.get('uploader', 'Unknown')}")
        self.log_message(f"  Available formats: {', '.join(available_formats)}")
        if available_resolutions:
            self.log_message(f"  Available resolutions: {', '.join(available_resolutions)}")
        if available_framerates:
            self.log_message(f"  Available framerates: {', '.join(available_framerates)}")
        if available_audio_bitrates:
            self.log_message(f"  Available audio bitrates: {', '.join(available_audio_bitrates)}")

    def _on_metadata_error(self, error_msg):
        """Handle metadata fetch error"""
        self.status_var.set("Failed to fetch video information")
        self.log_message(f"✗ Error: {error_msg}")
        messagebox.showerror("Fetch Error", f"Failed to fetch video information:\n{error_msg}")
        # Keep download button disabled on error
        self.metadata_fetched = False
        self.download_btn.configure(state='disabled')

    def _handle_playlist_detected(self, playlist_info, use_cache=False):
        """Handle detected playlist"""
        playlist_title = playlist_info.get('playlist_title', 'Playlist')
        n_entries = playlist_info.get('n_entries', 0)

        if use_cache:
            self.log_message(f"✓ Using cached playlist: {playlist_title}")
        else:
            self.status_var.set(f"Playlist detected: {playlist_title} ({n_entries} videos)")
            self.log_message(f"✓ Playlist detected: {playlist_title}")
            self.log_message(f"  Total videos: {n_entries}")

        # Show playlist selector dialog
        def on_videos_selected(selected_videos):
            """Handle video selection from playlist"""
            if not selected_videos:
                self.log_message("✗ No videos selected")
                return

            self.log_message(f"✓ Selected {len(selected_videos)} video(s) from playlist")

            # Store selected videos for download
            self.current_metadata['selected_videos'] = selected_videos
            self.current_metadata['is_playlist'] = True

            # Save selected video IDs for cache preservation
            self.selected_video_ids = {v.get('id', '') for v in selected_videos if v.get('id')}

            # Show metadata for first selected video
            first_video = selected_videos[0]
            self.metadata_title.configure(text=first_video.get('title', 'Unknown'))
            self.metadata_duration.configure(
                text=MetadataFetcher.format_duration(first_video.get('duration', 0))
            )
            self.metadata_uploader.configure(text=f"Playlist ({len(selected_videos)} videos)")
            self.metadata_views.configure(text="")

            # Load thumbnail
            thumbnail_url = first_video.get('thumbnail', '')
            if thumbnail_url:
                self._load_thumbnail(thumbnail_url)

            # Show metadata frame
            self.metadata_frame.grid()

            # Show format and quality sections
            self.format_label_frame.grid()
            self.quality_label_frame.grid()
            if hasattr(self, "other_options_frame"):
                self.other_options_frame.grid()

            # Enable download button
            self.metadata_fetched = True
            self.download_btn.configure(state='normal')

            self.status_var.set("Ready to download playlist videos")

        # Create and show playlist selector with initial selections
        PlaylistSelector(self.root, playlist_info, on_videos_selected,
                        initial_selected_ids=self.selected_video_ids)

    def _update_format_options(self, formats: list):
        """
        Update format selection options dynamically based on mode.
        Only shows formats from yt-dlp metadata, filtered by current mode.

        Args:
            formats: List of available format strings (e.g., ['MP4', 'WEBM', 'M4A'])
        """
        # Clear existing radio buttons safely (may fail during rapid resize)
        for widget in self.format_radio_frame.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass
        self.format_radios = []

        # Define format categories
        video_formats = ['mp4', 'webm', 'mkv', 'avi', 'mov', 'flv', 'mhtml']
        audio_formats = ['m4a', 'mp3', 'wav', 'aac', 'opus', 'vorbis', 'flac', 'ogg', 'weba']

        # Get current mode
        mode = self.mode_var.get() if hasattr(self, 'mode_var') else 'video_audio'

        # Filter formats based on mode
        filtered_formats = []
        for fmt in formats:
            fmt_lower = fmt.lower()
            if mode == 'audio':
                # Audio mode: only show audio formats
                if fmt_lower in audio_formats:
                    filtered_formats.append(fmt)
            elif mode == 'video':
                # Video mode: only show video formats
                if fmt_lower in video_formats:
                    filtered_formats.append(fmt)
            else:
                # Auto mode: show all formats
                filtered_formats.append(fmt)

        # If no formats after filtering, use defaults based on mode
        if not filtered_formats:
            if mode == 'audio':
                filtered_formats = ['M4A']
            else:
                filtered_formats = ['MP4']

        self.format_vars = {}
        self.format_checkboxes = []

        def select_format(fmt_value: str):
            for key, var in self.format_vars.items():
                var.set(key == fmt_value)
            self.format_var.set(fmt_value)

        # Create checkbox buttons for each format (exclusive selection)
        for fmt in filtered_formats:
            fmt_lower = fmt.lower()
            is_video = fmt_lower in video_formats
            var = tk.BooleanVar(value=False)
            checkbox = ctk.CTkCheckBox(
                self.format_radio_frame,
                text=f"🎥 {fmt.upper()}" if is_video else f"🎵 {fmt.upper()}",
                variable=var,
                command=lambda f=fmt_lower: select_format(f),
                checkbox_width=22, checkbox_height=22
            )
            self.format_checkboxes.append(checkbox)
            self.format_radios.append(checkbox)
            self.format_vars[fmt_lower] = var

        self._schedule_option_layout(self.format_radio_frame, self.format_checkboxes, min_col_width=120)
        if not getattr(self, "_format_options_bound", False):
            self.format_radio_frame.bind(
                "<Configure>",
                lambda e: self._schedule_option_layout(self.format_radio_frame, self.format_checkboxes, min_col_width=120)
            )
            self._format_options_bound = True

        # Set default value based on mode
        if mode == 'audio':
            # Prefer m4a for audio
            if 'm4a' in [f.lower() for f in filtered_formats]:
                select_format('m4a')
            else:
                select_format(filtered_formats[0].lower())
        else:
            # Prefer mp4 for video/video+audio
            if 'mp4' in [f.lower() for f in filtered_formats]:
                select_format('mp4')
            else:
                select_format(filtered_formats[0].lower())

    def _update_quality_options(self, display_names: list, values: list):
        """
        Update quality selection options dynamically

        Args:
            display_names: List of display names for quality options
            values: List of corresponding values for quality options
        """
        self.quality_combo.configure(values=display_names)
        self.quality_mapping = {name: val for name, val in zip(display_names, values)}

        if display_names:
            self.quality_combo.set(display_names[0])

    def _update_audio_bitrate_options(self, display_names: list, values: list):
        """
        Update audio bitrate selection options dynamically

        Args:
            display_names: List of display names for audio bitrate options
            values: List of corresponding values for audio bitrate options
        """
        self.audio_bitrate_combo.configure(values=display_names)
        self.audio_bitrate_mapping = {name: val for name, val in zip(display_names, values)}

        if display_names:
            self.audio_bitrate_combo.set(display_names[0])

    def _on_mode_changed(self):
        """Handle mode change (video/audio/auto)"""
        mode = self.mode_var.get()
        if mode == "audio":
            self.format_var.set("mp3")
            # Show audio bitrate for audio mode
            self.audio_bitrate_frame.grid()
        elif mode == "video":
            # Hide audio bitrate for video-only mode
            self.audio_bitrate_frame.grid_remove()
        else:  # auto mode
            # Show audio bitrate for auto mode
            self.audio_bitrate_frame.grid()

        # Update format options based on mode
        self._update_format_options(self.current_metadata.get('available_formats', ['MP4', 'MP3'])
                                   if self.current_metadata else ['MP4', 'MP3'])

        # Update convert format options based on mode
        self._update_convert_format_options()

    def _on_url_changed(self, event=None, force: bool = False):
        """Handle URL entry changes for auto-fetch"""
        url = self.url_entry.get().strip()

        # Cancel previous timer if exists
        if self.auto_fetch_timer:
            self.root.after_cancel(self.auto_fetch_timer)

        if not force and url == self.last_url_value:
            return

        self.last_url_value = url

        # Check if URL is valid
        if url and self.is_valid_url(url):
            # Schedule auto-fetch after 1 second of no typing
            self.auto_fetch_timer = self.root.after(1000, self.fetch_video_info)
        else:
            # Hide format/quality sections if URL is invalid
            if not url:
                self.format_label_frame.grid_remove()
                self.quality_label_frame.grid_remove()
                self.metadata_frame.grid_remove()
                self.trim_frame.grid_remove()
                self.convert_frame.grid_remove()
                self.download_btn.configure(state='disabled')
                self.metadata_fetched = False

    def _toggle_trim_controls(self):
        """Toggle trim control states"""
        if self.trim_enabled.get():
            self.trim_start_entry.configure(state='normal')
            self.trim_end_entry.configure(state='normal')
        else:
            self.trim_start_entry.configure(state='disabled')
            self.trim_end_entry.configure(state='disabled')

    def log_message(self, message):
        """
        Add message to output log

        Args:
            message: Message to log
        """
        self.output_text.configure(state='normal')
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.output_text.configure(state='disabled')

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """
        Validate if the input is a valid URL

        Args:
            url: URL string to validate

        Returns:
            True if URL is valid, False otherwise
        """
        if not url or not isinstance(url, str):
            return False

        url = url.strip()

        # Check for common video URL patterns
        video_url_patterns = [
            r'https?://(www\.)?youtube\.com',
            r'https?://(www\.)?youtu\.be',
            r'https?://(www\.)?vimeo\.com',
            r'https?://(www\.)?dailymotion\.com',
            r'https?://(www\.)?twitch\.tv',
            r'https?://(www\.)?tiktok\.com',
            r'https?://(www\.)?instagram\.com',
            r'https?://(www\.)?facebook\.com',
            r'https?://(www\.)?twitter\.com',
            r'https?://(www\.)?x\.com',
            r'https?://(www\.)?reddit\.com',
            r'https?://(www\.)?bilibili\.com',
            r'https?://(www\.)?nicovideo\.jp',
            r'https?://',  # Generic http/https URL
        ]

        for pattern in video_url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True

        return False

    def validate_inputs(self):
        """
        Validate user inputs before download
        
        Returns:
            True if all inputs are valid, False otherwise
        """
        yt_dlp_path = self.yt_dlp_entry.get().strip()
        url = self.url_entry.get().strip()
        output_dir = self.output_entry.get().strip()
        
        if not yt_dlp_path:
            messagebox.showerror("Error", "Please select yt-dlp executable path")
            return False
        
        if not os.path.exists(yt_dlp_path):
            messagebox.showerror("Error", "yt-dlp executable not found at specified path")
            return False
        
        if not url:
            messagebox.showerror("Error", "Please enter a video URL")
            return False
        
        if not output_dir:
            messagebox.showerror("Error", "Please select an output directory")
            return False
        
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception:
                messagebox.showerror("Error", "Cannot create output directory")
                return False
        
        return True
    
    def start_download(self):
        """Start download process"""
        if not self.validate_inputs():
            return

        # Check if using a custom template
        if self.current_template_command:
            self._start_template_download()
            return

        # Disable download button and enable cancel button during download
        self.download_btn.configure(state='disabled')
        self.cancel_btn.configure(state='normal')
        self.status_var.set("Downloading...")

        # Show and start progress bar
        self.download_progress_frame.grid()
        self.download_progress_label.configure(text="Preparing download...")
        self.download_progress_bar.set(0)  # Reset progress bar

        # Switch to log tab
        self.tabview.set("📄 Output Log")

        # Clear previous output
        self.output_text.configure(state='normal')
        self.output_text.delete(1.0, tk.END)
        self.output_text.configure(state='disabled')

        # Get parameters
        yt_dlp_path = self.yt_dlp_entry.get().strip()
        url = self.url_entry.get().strip()
        output_dir = self.output_entry.get().strip()
        format_type = self.format_var.get()

        # Get quality value from mapping
        quality_display = self.quality_var.get()
        quality = self.quality_mapping.get(quality_display, "best")

        # Get trim parameters
        trim_start = None
        trim_end = None
        if self.trim_enabled.get():
            trim_start = self.trim_start_entry.get().strip()
            trim_end = self.trim_end_entry.get().strip()

            # Validate time format (allow empty fields)
            if trim_start and not self._validate_time_format(trim_start):
                messagebox.showerror("Invalid Time", "Please use HH:MM:SS format for start time")
                self.download_btn.configure(state='normal')
                self.status_var.set("Ready")
                return

            if trim_end and not self._validate_time_format(trim_end):
                messagebox.showerror("Invalid Time", "Please use HH:MM:SS format for end time")
                self.download_btn.configure(state='normal')
                self.status_var.set("Ready")
                return

            # Convert empty strings to None
            trim_start = trim_start if trim_start else None
            trim_end = trim_end if trim_end else None

        # Get mode (video/audio/auto)
        mode = self.mode_var.get()

        # Get convert options
        convert_enabled = self.convert_enabled.get()
        convert_format = self.convert_format_var.get() if convert_enabled else ""

        # Other options
        save_thumbnail_file = self.save_thumbnail_var.get() if hasattr(self, 'save_thumbnail_var') else False
        save_subtitles = self.save_subtitles_var.get() if hasattr(self, 'save_subtitles_var') else False

        # SponsorBlock options
        sponsorblock_enabled = self.sponsorblock_enabled.get() if hasattr(self, 'sponsorblock_enabled') else False
        sponsorblock_mode = self.sponsorblock_mode_var.get() if hasattr(self, 'sponsorblock_mode_var') else "mark"
        sponsorblock_categories = []
        if sponsorblock_enabled and hasattr(self, 'sponsorblock_categories'):
            sponsorblock_categories = [
                key for key, var in self.sponsorblock_categories.items() if var.get()
            ]
            if not sponsorblock_categories:
                messagebox.showerror("SponsorBlock", "Please select at least one category to block.")
                self.download_btn.configure(state='normal')
                self.status_var.set("Ready")
                return

        # Check if this is a playlist download
        if self.current_metadata.get('is_playlist', False):
            selected_videos = self.current_metadata.get('selected_videos', [])
            self._start_playlist_download(
                yt_dlp_path=yt_dlp_path,
                selected_videos=selected_videos,
                output_dir=output_dir,
                format_type=format_type,
                quality=quality,
                trim_start=trim_start,
                trim_end=trim_end,
                mode=mode,
                convert_enabled=convert_enabled,
                convert_format=convert_format,
                save_thumbnail_file=save_thumbnail_file,
                save_subtitles=save_subtitles,
                sponsorblock_enabled=sponsorblock_enabled,
                sponsorblock_mode=sponsorblock_mode,
                sponsorblock_categories=sponsorblock_categories
            )
            return

        # Start download
        self.downloader.download(
            yt_dlp_path=yt_dlp_path,
            url=url,
            output_dir=output_dir,
            format_type=format_type,
            quality=quality,
            trim_start=trim_start,
            trim_end=trim_end,
            on_log=self.log_message,
            on_complete=self._on_download_complete,
            on_error=self._on_download_error,
            on_download_started=self._on_download_started,
            on_progress=self._on_download_progress,
            mode=mode,
            convert_enabled=convert_enabled,
            convert_format=convert_format,
            save_thumbnail_file=save_thumbnail_file,
            save_subtitles=save_subtitles,
            sponsorblock_enabled=sponsorblock_enabled,
            sponsorblock_mode=sponsorblock_mode,
            sponsorblock_categories=sponsorblock_categories
        )

    def _start_playlist_download(self, yt_dlp_path, selected_videos, output_dir, format_type, quality, trim_start, trim_end, mode, convert_enabled=False, convert_format="", save_thumbnail_file=False, save_subtitles=False, sponsorblock_enabled=False, sponsorblock_mode="mark", sponsorblock_categories=None):
        """Start downloading multiple videos from a playlist"""
        import threading
        sponsorblock_categories = sponsorblock_categories or []

        def download_playlist_thread():
            """Download videos in a separate thread"""
            total_videos = len(selected_videos)
            download_event = threading.Event()
            download_error = [False]  # Use list to allow modification in nested function

            def on_video_complete():
                """Called when a single video download completes"""
                download_event.set()

            def on_video_error(error_msg):
                """Called when a video download fails"""
                download_error[0] = True
                download_event.set()

            for idx, video in enumerate(selected_videos, 1):
                video_url = video.get('url', '')
                video_title = video.get('title', 'Unknown')

                self.log_message(f"\n{'='*70}")
                self.log_message(f"Downloading video {idx}/{total_videos}: {video_title}")
                self.log_message(f"{'='*70}")

                # Update progress label
                self.download_progress_label.configure(
                    text=f"Downloading {idx}/{total_videos}: {video_title[:50]}..."
                )
                self.download_progress_bar.set((idx - 1) / total_videos)

                # Reset event for this download
                download_event.clear()
                download_error[0] = False

                # Download this video
                self.downloader.download(
                    yt_dlp_path=yt_dlp_path,
                    url=video_url,
                    output_dir=output_dir,
                    format_type=format_type,
                    quality=quality,
                    trim_start=trim_start,
                    trim_end=trim_end,
                    on_log=self.log_message,
                    on_complete=on_video_complete,
                    on_error=on_video_error,
                    on_download_started=self._on_download_started,
                    on_progress=self._on_download_progress,
                    mode=mode,
                    is_playlist_item=True,
                    convert_enabled=convert_enabled,
                    convert_format=convert_format,
                    save_thumbnail_file=save_thumbnail_file,
                    save_subtitles=save_subtitles,
                    sponsorblock_enabled=sponsorblock_enabled,
                    sponsorblock_mode=sponsorblock_mode,
                    sponsorblock_categories=sponsorblock_categories
                )

                # Wait for this video to complete
                download_event.wait()

                # If error occurred, stop downloading
                if download_error[0]:
                    self.log_message(f"\n✗ Error downloading video {idx}, stopping playlist download")
                    break

            # All videos downloaded
            self.download_progress_bar.set(1.0)
            self.download_progress_label.configure(text=f"Completed downloading {total_videos} videos")
            self.log_message(f"\n{'='*70}")
            self.log_message(f"✓ Playlist download complete! Downloaded {total_videos} videos")
            self.log_message(f"{'='*70}")

            # Re-enable download button
            self.download_btn.configure(state='normal')
            self.cancel_btn.configure(state='disabled')
            self.status_var.set("Playlist download complete")

            # Show completion message
            self.root.after(0, lambda: messagebox.showinfo("Download Complete",
                f"Successfully downloaded {total_videos} videos from the playlist!"))

            # Hide progress bar after notification
            self.root.after(0, lambda: self.download_progress_frame.grid_remove())

        # Start download in separate thread
        thread = threading.Thread(target=download_playlist_thread, daemon=True)
        thread.start()

    def _start_template_download(self):
        """Start download using custom template"""
        import subprocess
        import threading

        # Disable download button during download
        self.download_btn.configure(state='disabled')
        self.status_var.set("Downloading with template...")

        # Show and start progress bar
        self.download_progress_frame.grid()
        self.download_progress_label.configure(text="Downloading with custom template...")
        self.download_progress_bar.set(0)

        # Switch to log tab
        self.tabview.set("📄 Output Log")

        # Clear previous output
        self.output_text.configure(state='normal')
        self.output_text.delete(1.0, tk.END)
        self.output_text.configure(state='disabled')

        # Get parameters
        yt_dlp_path = self.yt_dlp_entry.get().strip()
        url = self.url_entry.get().strip()
        output_dir = self.output_entry.get().strip()

        # Build command with template
        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

        # Parse template command and build full command
        import shlex
        template_args = shlex.split(self.current_template_command)

        cmd = [yt_dlp_path] + template_args + ["-o", output_template, url]

        self.log_message(f"Using custom template command:")
        self.log_message(f"{' '.join(cmd)}\n")
        self.log_message("-" * 70)

        def download_thread():
            try:
                # Execute command
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
                    self.log_message(line.rstrip())

                    # Parse progress from yt-dlp output
                    if '[download]' in line:
                        progress_info = self._parse_template_progress_line(line)
                        if progress_info:
                            percent = progress_info.get('percent', 0)
                            speed = progress_info.get('speed', 'N/A')
                            eta = progress_info.get('eta', 'N/A')
                            downloaded = progress_info.get('downloaded', 'N/A')
                            total = progress_info.get('total', 'N/A')

                            self.download_progress_bar.set(percent / 100.0)
                            progress_text = f"Downloading... {percent:.1f}% | {downloaded} / {total} | {speed} | ETA {eta}"
                            self.download_progress_label.configure(text=progress_text)

                process.wait()

                if process.returncode == 0:
                    self.log_message("-" * 70)
                    self.log_message("✓ Download completed successfully!")
                    self._on_download_complete()
                else:
                    self.log_message("-" * 70)
                    self.log_message(f"✗ Download failed with error code: {process.returncode}")
                    self._on_download_error("Check the output log for details")

            except Exception as e:
                self.log_message(f"✗ Error: {str(e)}")
                self._on_download_error(str(e))

            finally:
                pass

        # Start in thread
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()
    
    def _on_download_started(self):
        """Callback when actual download starts (after preparation)"""
        self.download_progress_label.configure(text="Downloading...")

    def _on_download_progress(self, progress_info):
        """Callback for download progress updates

        Args:
            progress_info: Dictionary with keys: 'percent', 'speed', 'eta', 'downloaded', 'total'
        """
        percent = progress_info.get('percent', 0)
        speed = progress_info.get('speed', 'N/A')
        eta = progress_info.get('eta', 'N/A')
        downloaded = progress_info.get('downloaded', 'N/A')
        total = progress_info.get('total', 'N/A')

        self.download_progress_bar.set(percent / 100.0)

        # Format: "Downloading... 45.3% | 123.45MiB / 456.78MiB | 1.23MiB/s | ETA 00:30"
        progress_text = f"Downloading... {percent:.1f}% | {downloaded} / {total} | {speed} | ETA {eta}"
        self.download_progress_label.configure(text=progress_text)

    def _parse_template_progress_line(self, line: str):
        """Parse progress information from yt-dlp output line for template downloads

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

            # Calculate downloaded size from percentage and total
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

    def _on_download_complete(self):
        """Callback when download completes successfully"""
        self.status_var.set("Download completed!")
        self.download_btn.configure(state='normal')
        self.cancel_btn.configure(state='disabled')

        # Set progress bar to 100% and hide
        self.download_progress_bar.set(1.0)
        self.download_progress_label.configure(text="✓ Download completed!")
        # Keep progress visible for a moment, then hide
        self.root.after(2000, self.download_progress_frame.grid_remove)

        messagebox.showinfo("Success", "Download completed successfully!")

    def _on_download_error(self, error_msg):
        """
        Callback when download fails

        Args:
            error_msg: Error message
        """
        self.status_var.set("Download failed!")
        self.download_btn.configure(state='normal')
        self.cancel_btn.configure(state='disabled')

        # Hide progress bar
        self.download_progress_label.configure(text="✗ Download failed!")
        self.root.after(2000, self.download_progress_frame.grid_remove)

        messagebox.showerror("Error", f"Download failed: {error_msg}")

    def cancel_download(self):
        """Cancel the current download"""
        self.downloader.cancel_download()
        self.cancel_btn.configure(state='disabled')
        self.status_var.set("Cancelling download...")

    def _format_speed(self, speed_bytes_per_sec):
        """Format download speed in human-readable format

        Args:
            speed_bytes_per_sec: Speed in bytes per second

        Returns:
            Formatted speed string (e.g., "1.23MiB/s")
        """
        if speed_bytes_per_sec < 1024:
            return f"{speed_bytes_per_sec:.2f}B/s"
        elif speed_bytes_per_sec < 1024 * 1024:
            return f"{speed_bytes_per_sec / 1024:.2f}KiB/s"
        else:
            return f"{speed_bytes_per_sec / (1024 * 1024):.2f}MiB/s"

    def _format_time(self, seconds):
        """Format time in human-readable format

        Args:
            seconds: Time in seconds

        Returns:
            Formatted time string (e.g., "00:30" or "01:23:45")
        """
        if seconds < 0:
            return "N/A"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def _validate_time_format(self, time_str):
        """
        Validate time format HH:MM:SS

        Args:
            time_str: Time string to validate

        Returns:
            True if valid, False otherwise
        """
        import re
        pattern = r'^\d{1,2}:\d{2}:\d{2}$'
        if not re.match(pattern, time_str):
            return False

        parts = time_str.split(':')
        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])

            if minutes >= 60 or seconds >= 60:
                return False

            return True
        except ValueError:
            return False

    def _load_thumbnail(self, url):
        """
        Load and display video thumbnail

        Args:
            url: URL of the thumbnail image
        """
        if not PIL_AVAILABLE:
            self.log_message("⚠ PIL/Pillow not installed - thumbnail display disabled")
            return

        try:
            # Download thumbnail
            with urllib.request.urlopen(url, timeout=10) as response:
                image_data = response.read()

            # Open image with PIL
            image = Image.open(BytesIO(image_data))

            # Resize to compact size (max 120x90, maintain aspect ratio)
            image.thumbnail((120, 90), Image.Resampling.LANCZOS)

            # Convert to CTkImage for proper HiDPI scaling
            photo = ctk.CTkImage(light_image=image, dark_image=image,
                                 size=(image.width, image.height))

            # Keep a reference to prevent garbage collection
            self.thumbnail_photo = photo

            # Display in label
            self.thumbnail_label.configure(image=photo)

            self.log_message("✓ Thumbnail loaded")

        except Exception as e:
            self.log_message(f"⚠ Could not load thumbnail: {str(e)}")

    def _check_scrollbar_needed(self):
        """Check if scrollbar is needed and show/hide accordingly.
        Note: CTkScrollableFrame handles its own scrollbar automatically."""
        pass

    def _resize_window_for_metadata(self):
        """Resize window to accommodate metadata and trim sections"""
        try:
            # Update the window to get accurate measurements
            self.root.update_idletasks()

            # Get current window size
            current_width = self.root.winfo_width()
            current_height = self.root.winfo_height()

            # Calculate required height for content
            required_height = self.root.winfo_reqheight()

            # If current height is less than required, expand the window
            if current_height < required_height:
                # Add some padding for comfort
                new_height = min(required_height + 20, 700)  # Cap at 700px
                self.root.geometry(f"{current_width}x{new_height}")
        except:
            pass  # Ignore errors during resize

