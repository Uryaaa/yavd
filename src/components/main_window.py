"""Main application window"""

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import os
import shutil
import subprocess
import threading
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

        # Template mode state
        self.template_active = False

        # Playlist caching - avoid re-fetching same playlist
        self.cached_playlist_url = ''
        self.cached_playlist_data = None
        self.selected_video_ids = set()  # Preserve selections when re-opening

        # Quick queue state
        self.url_queue = []
        self.is_queue_downloading = False

        # Recent history (display label + URL)
        self.recent_history = []
        self.recent_label_to_url = {}

        # Auto-fetch and helper state
        self.auto_fetch_on_paste = True
        self._auto_fetch_after_id = None

        # Quick preset state
        self.quick_preset_active = None
        self.max_recent_links = 10

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

        self._restore_recent_urls()
        self._refresh_recent_url_combo()
        self._refresh_queue_ui()
        self._refresh_tool_status()
        self._update_filename_preview()

        # Smart paste: prefill URL on startup if clipboard contains a valid URL
        self.root.after(250, self._prefill_url_from_clipboard)

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

        if active and self.quick_preset_active:
            self._clear_quick_preset()

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

    def _get_quick_presets(self):
        """Quick preset definitions."""
        return {
            "best_mp4": {"label": "Best MP4", "mode": "video_audio", "format": "mp4", "quality": "best"},
            "audio_mp3": {"label": "Audio MP3", "mode": "audio", "format": "mp3", "quality": "best"},
            "audio_opus": {"label": "Audio Opus", "mode": "audio", "format": "opus", "quality": "best"},
            "small_mp4": {"label": "Small MP4", "mode": "video_audio", "format": "mp4", "quality": "480"},
        }

    def _set_quick_preset_mode(self, preset_key: str, preset_label: str):
        """Show active quick preset state and lock relevant controls."""
        self.quick_preset_active = preset_key
        if hasattr(self, "quick_preset_mode_label"):
            self.quick_preset_mode_label.configure(
                text=f"Preset active: {preset_label} - options locked"
            )
        if hasattr(self, "quick_preset_mode_frame"):
            self.quick_preset_mode_frame.grid()

        if hasattr(self, "mode_frame"):
            self._set_section_state(self.mode_frame, "disabled")
        if hasattr(self, "format_frame"):
            self._set_section_state(self.format_frame, "disabled")
        if hasattr(self, "quality_label_frame"):
            self._set_section_state(self.quality_label_frame, "disabled")
        if hasattr(self, "convert_frame"):
            self._set_section_state(self.convert_frame, "disabled")

    def _clear_quick_preset(self):
        """Clear active quick preset and unlock controls."""
        self.quick_preset_active = None
        if hasattr(self, "quick_preset_mode_frame"):
            self.quick_preset_mode_frame.grid_remove()

        if not self.template_active:
            if hasattr(self, "mode_frame"):
                self._set_section_state(self.mode_frame, "normal")
            if hasattr(self, "format_frame"):
                self._set_section_state(self.format_frame, "normal")
            if hasattr(self, "quality_label_frame"):
                self._set_section_state(self.quality_label_frame, "normal")
            if hasattr(self, "convert_frame"):
                self._set_section_state(self.convert_frame, "normal")

    def _reapply_active_quick_preset(self):
        """Re-apply active preset values after metadata refresh."""
        if not self.quick_preset_active:
            return
        preset = self._get_quick_presets().get(self.quick_preset_active)
        if not preset:
            return

        self._set_mode(preset["mode"])
        fmt = preset["format"]
        if hasattr(self, "format_vars") and fmt in self.format_vars:
            for key, var in self.format_vars.items():
                var.set(key == fmt)
        self.format_var.set(fmt)
        self._set_quality_by_value(preset["quality"])

        if hasattr(self, "convert_enabled"):
            self.convert_enabled.set(False)
            self._toggle_convert_controls()


    def _load_user_settings(self):
        """Load user settings from config and apply to UI."""
        # Output directory
        saved_output = self.config.get('output_dir', '')
        if saved_output:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, saved_output)

        # After-download behavior
        saved_after_action = self.config.get('after_download_action', 'Do nothing')
        if hasattr(self, 'after_download_combo'):
            allowed = ["Do nothing", "Open folder", "Copy file path"]
            if saved_after_action not in allowed:
                saved_after_action = "Do nothing"
            self.after_download_combo.set(saved_after_action)

        if hasattr(self, 'filename_style_combo'):
            saved_style = self.config.get('filename_style', 'classic')
            allowed_styles = ["classic", "basic", "pretty", "nerdy"]
            if saved_style not in allowed_styles:
                saved_style = "classic"
            self.filename_style_combo.set(saved_style)

        if hasattr(self, 'keep_original_var'):
            self.keep_original_var.set(bool(self.config.get('keep_original_file', False)))
        if hasattr(self, 'write_description_var'):
            self.write_description_var.set(bool(self.config.get('write_description_file', False)))
        if hasattr(self, 'embed_chapters_var'):
            self.embed_chapters_var.set(bool(self.config.get('embed_chapters', False)))
        if hasattr(self, 'skip_existing_var'):
            self.skip_existing_var.set(bool(self.config.get('skip_existing_files', False)))
        if hasattr(self, 'allow_duplicates_var'):
            self.allow_duplicates_var.set(bool(self.config.get('allow_duplicate_files', False)))
            self._toggle_duplicate_mode()

        self.auto_fetch_on_paste = bool(self.config.get('auto_fetch_on_paste', True))

    def _bind_setting_savers(self):
        """Bind UI changes to persist settings."""
        def save_output_dir(_event=None):
            self.config.set('output_dir', self.output_entry.get().strip())
            self._update_filename_preview()

        self.output_entry.bind("<FocusOut>", save_output_dir)
        self.output_entry.bind("<Return>", save_output_dir)

        def save_ytdlp_path(_event=None):
            self.config.set('yt_dlp_path', self.yt_dlp_entry.get().strip())
            self._refresh_tool_status()

        self.yt_dlp_entry.bind("<FocusOut>", save_ytdlp_path)
        self.yt_dlp_entry.bind("<Return>", save_ytdlp_path)
        self.url_entry.bind("<Return>", lambda _e: self.fetch_video_info())
        self.url_entry.bind("<FocusOut>", lambda _e: self._remember_recent_url(self.url_entry.get().strip()))
        self.output_entry.bind("<KeyRelease>", lambda _e: self._update_filename_preview())

        if hasattr(self, 'filename_style_var'):
            self.filename_style_var.trace_add(
                "write",
                lambda *_: self._on_filename_style_changed(self.filename_style_var.get())
            )

        if hasattr(self, 'keep_original_var'):
            self.keep_original_var.trace_add(
                "write",
                lambda *_: self.config.set('keep_original_file', bool(self.keep_original_var.get()))
            )
        if hasattr(self, 'write_description_var'):
            self.write_description_var.trace_add(
                "write",
                lambda *_: self.config.set('write_description_file', bool(self.write_description_var.get()))
            )
        if hasattr(self, 'embed_chapters_var'):
            self.embed_chapters_var.trace_add(
                "write",
                lambda *_: self.config.set('embed_chapters', bool(self.embed_chapters_var.get()))
            )
        if hasattr(self, 'skip_existing_var'):
            self.skip_existing_var.trace_add(
                "write",
                lambda *_: self.config.set('skip_existing_files', bool(self.skip_existing_var.get()))
            )
        if hasattr(self, 'allow_duplicates_var'):
            self.allow_duplicates_var.trace_add(
                "write",
                lambda *_: (
                    self.config.set('allow_duplicate_files', bool(self.allow_duplicates_var.get())),
                    self._toggle_duplicate_mode()
                )
            )

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

    def _on_after_download_action_changed(self, selected_action):
        """Persist selected post-download behavior."""
        self.config.set('after_download_action', selected_action)

    def _on_filename_style_changed(self, selected_style):
        """Persist filename style and refresh preview."""
        self.config.set('filename_style', selected_style)
        self._update_filename_preview()

    def _toggle_duplicate_mode(self):
        """Keep duplicate mode opposite to skip-existing mode."""
        allow_duplicates = bool(self.allow_duplicates_var.get()) if hasattr(self, 'allow_duplicates_var') else False

        if hasattr(self, 'skip_existing_checkbox'):
            if allow_duplicates:
                if hasattr(self, 'skip_existing_var'):
                    self.skip_existing_var.set(False)
                self.skip_existing_checkbox.configure(state='disabled')
            else:
                self.skip_existing_checkbox.configure(state='normal')

    def _restore_recent_urls(self):
        """Load recent history from config with backward compatibility."""
        loaded_items = []

        saved_history = self.config.get('recent_history', [])
        if isinstance(saved_history, list):
            for item in saved_history:
                if not isinstance(item, dict):
                    continue
                url = (item.get('url') or '').strip()
                if not url:
                    continue
                title = (item.get('title') or url).strip()
                platform = (item.get('platform') or self._get_platform_from_url(url)).strip()
                loaded_items.append({
                    "url": url,
                    "title": title,
                    "platform": platform,
                })

        if not loaded_items:
            # Fallback for older config format
            saved_urls = self.config.get('recent_urls', [])
            if isinstance(saved_urls, list):
                for url in saved_urls:
                    if not isinstance(url, str) or not url.strip():
                        continue
                    normalized = url.strip()
                    loaded_items.append({
                        "url": normalized,
                        "title": normalized,
                        "platform": self._get_platform_from_url(normalized),
                    })

        self.recent_history = loaded_items[:self.max_recent_links]

    def _get_platform_from_url(self, url: str) -> str:
        """Get human-readable platform from URL."""
        try:
            netloc = (urlparse(url).netloc or "").lower()
        except Exception:
            return "Unknown"

        netloc = netloc.replace("www.", "")
        platform_map = {
            "youtube.com": "YouTube",
            "youtu.be": "YouTube",
            "x.com": "X/Twitter",
            "twitter.com": "X/Twitter",
            "instagram.com": "Instagram",
            "tiktok.com": "TikTok",
            "facebook.com": "Facebook",
            "reddit.com": "Reddit",
            "vimeo.com": "Vimeo",
            "dailymotion.com": "Dailymotion",
            "twitch.tv": "Twitch",
            "bilibili.com": "Bilibili",
            "nicovideo.jp": "Niconico",
        }
        for domain, label in platform_map.items():
            if netloc == domain or netloc.endswith(f".{domain}"):
                return label

        if netloc:
            return netloc.split(".")[0].capitalize()
        return "Unknown"

    def _build_recent_label(self, item: dict) -> str:
        """Build display label for recent history item."""
        title = (item.get("title") or item.get("url") or "Video").strip()
        platform = (item.get("platform") or self._get_platform_from_url(item.get("url", ""))).strip()
        if len(title) > 55:
            title = title[:52] + "..."
        return f"{title} - {platform}"

    def _refresh_recent_url_combo(self):
        """Refresh recent URL dropdown values."""
        if not hasattr(self, 'recent_url_combo'):
            return

        self.recent_label_to_url = {}
        values = []
        for item in self.recent_history:
            base_label = self._build_recent_label(item)
            label = base_label
            index = 2
            while label in self.recent_label_to_url:
                label = f"{base_label} ({index})"
                index += 1
            self.recent_label_to_url[label] = item.get("url", "")
            values.append(label)

        if not values:
            values = [""]
        self.recent_url_combo.configure(values=values)
        if self.recent_history:
            self.recent_url_combo.set(values[0])
        else:
            self.recent_url_combo.set("")

    def _on_recent_url_selected(self, value):
        """Apply URL from recent dropdown."""
        selected = (value or "").strip()
        if not selected:
            return

        selected_url = self.recent_label_to_url.get(selected, "")
        if not selected_url and self.is_valid_url(selected):
            selected_url = selected
        if not selected_url:
            return

        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, selected_url)
        self._update_filename_preview()

    def _clear_recent_urls(self):
        """Clear all recent URLs from memory and config."""
        if not self.recent_history:
            self.status_var.set("No recent links to clear")
            return

        if not messagebox.askyesno("Clear Recent Links", "Remove all recent links?"):
            return

        self.recent_history = []
        self.recent_label_to_url = {}
        self.config.set('recent_history', [])
        self.config.set('recent_urls', [])
        self._refresh_recent_url_combo()
        self.status_var.set("Recent links cleared")
        self.log_message("Recent links cleared")

    def _remember_recent_url(self, url: str, title: str = "", platform: str = ""):
        """Store URL in recent history."""
        normalized = (url or "").strip()
        if not normalized or not self.is_valid_url(normalized):
            return

        existing = None
        for item in self.recent_history:
            if item.get("url") == normalized:
                existing = item
                break

        if not title:
            title = existing.get("title", normalized) if existing else normalized
        if not platform:
            platform = existing.get("platform", self._get_platform_from_url(normalized)) if existing else self._get_platform_from_url(normalized)

        self.recent_history = [item for item in self.recent_history if item.get("url") != normalized]
        self.recent_history.insert(0, {
            "url": normalized,
            "title": title.strip() or normalized,
            "platform": platform.strip() or self._get_platform_from_url(normalized),
        })
        self.recent_history = self.recent_history[:self.max_recent_links]

        self.config.set('recent_history', self.recent_history)
        self.config.set('recent_urls', [item.get("url", "") for item in self.recent_history])
        self._refresh_recent_url_combo()

    def _prefill_url_from_clipboard(self):
        """Auto-fill URL from clipboard on startup when the URL field is empty."""
        try:
            if self.url_entry.get().strip():
                return
            clipboard_text = self.root.clipboard_get().strip()
        except tk.TclError:
            return

        if not self.is_valid_url(clipboard_text):
            return

        self.url_entry.insert(0, clipboard_text)
        self.log_message("Clipboard URL detected and prefilled")
        self._update_filename_preview()

        if self.auto_fetch_on_paste and self.yt_dlp_entry.get().strip():
            self.fetch_video_info()

    def _on_url_changed(self):
        """Compatibility hook for URL updates."""
        self._update_filename_preview()

    def _set_mode(self, mode: str):
        """Set download mode and refresh dependent controls."""
        if not hasattr(self, "mode_vars"):
            return
        for key, var in self.mode_vars.items():
            var.set(key == mode)
        self.mode_var.set(mode)
        self._on_mode_changed()

    def _set_quality_by_value(self, quality_value: str):
        """Select a quality option by internal value."""
        for display, value in self.quality_mapping.items():
            if value == quality_value:
                self.quality_combo.set(display)
                self.quality_var.set(display)
                return
        values = self.quality_combo.cget("values")
        if values:
            self.quality_combo.set(values[0])

    def _apply_quick_preset(self, preset_key: str):
        """Apply one-click download preset."""
        preset = self._get_quick_presets().get(preset_key)
        if not preset:
            return

        if self.template_active:
            self._clear_template_mode()

        if not self.current_metadata:
            self._update_format_options(['MP4', 'MP3', 'M4A', 'OPUS'])

        self._set_quick_preset_mode(preset_key, preset["label"])
        self._reapply_active_quick_preset()

        self._update_filename_preview()
        self.log_message(f"Preset applied: {preset['label']}")

    def _add_current_url_to_queue(self):
        """Add current URL to simple queue."""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Queue", "Please enter a URL first.")
            return
        if not self.is_valid_url(url):
            messagebox.showwarning("Queue", "Please enter a valid URL.")
            return
        if any(item.get("url") == url for item in self.url_queue):
            self.status_var.set("URL already in queue")
            return

        title = url
        if self.current_metadata and not self.current_metadata.get("is_playlist", False):
            title = self.current_metadata.get("title", url)

        self.url_queue.append({"url": url, "title": title})
        self._remember_recent_url(url, title=title, platform=self._get_platform_from_url(url))
        self._refresh_queue_ui()
        self.status_var.set(f"Added to queue ({len(self.url_queue)})")

    def _clear_url_queue(self):
        """Clear queued URLs."""
        if self.is_queue_downloading:
            messagebox.showwarning("Queue", "Queue is currently downloading.")
            return
        self.url_queue.clear()
        self._refresh_queue_ui()
        self.status_var.set("Queue cleared")

    def _refresh_queue_ui(self):
        """Refresh queue count and preview text."""
        count = len(self.url_queue)
        if hasattr(self, "queue_status_label"):
            self.queue_status_label.configure(text=f"Queue: {count}")

        if hasattr(self, "queue_preview_text"):
            self.queue_preview_text.configure(state='normal')
            self.queue_preview_text.delete("1.0", tk.END)
            if count == 0:
                self.queue_preview_text.insert(tk.END, "No queued URLs")
            else:
                preview_items = self.url_queue[:5]
                for idx, item in enumerate(preview_items, 1):
                    title = item.get("title") or item.get("url", "")
                    self.queue_preview_text.insert(tk.END, f"{idx}. {title}\n")
                if count > 5:
                    self.queue_preview_text.insert(tk.END, f"...and {count - 5} more")
            self.queue_preview_text.configure(state='disabled')

    def _collect_download_settings(self):
        """Collect and validate current download settings."""
        # Get parameters
        format_type = self.format_var.get()
        output_dir = self.output_entry.get().strip()

        # Get quality value from mapping
        quality_display = self.quality_var.get()
        quality = self.quality_mapping.get(quality_display, "best")

        # Get trim parameters
        trim_start = None
        trim_end = None
        if self.trim_enabled.get():
            trim_start = self.trim_start_entry.get().strip()
            trim_end = self.trim_end_entry.get().strip()

            if trim_start and not self._validate_time_format(trim_start):
                messagebox.showerror("Invalid Time", "Please use HH:MM:SS format for start time")
                return None

            if trim_end and not self._validate_time_format(trim_end):
                messagebox.showerror("Invalid Time", "Please use HH:MM:SS format for end time")
                return None

            trim_start = trim_start if trim_start else None
            trim_end = trim_end if trim_end else None

        mode = self.mode_var.get()
        convert_enabled = self.convert_enabled.get()
        convert_format = self.convert_format_var.get() if convert_enabled else ""
        save_thumbnail_file = self.save_thumbnail_var.get() if hasattr(self, 'save_thumbnail_var') else False
        save_subtitles = self.save_subtitles_var.get() if hasattr(self, 'save_subtitles_var') else False
        embed_chapters = self.embed_chapters_var.get() if hasattr(self, 'embed_chapters_var') else False
        keep_original_file = self.keep_original_var.get() if hasattr(self, 'keep_original_var') else False
        write_description = self.write_description_var.get() if hasattr(self, 'write_description_var') else False
        skip_existing = self.skip_existing_var.get() if hasattr(self, 'skip_existing_var') else False
        allow_duplicates = self.allow_duplicates_var.get() if hasattr(self, 'allow_duplicates_var') else False
        if allow_duplicates:
            skip_existing = False
        output_template = self._build_output_template(output_dir)
        audio_quality_display = self.audio_bitrate_var.get() if hasattr(self, 'audio_bitrate_var') else "best"
        audio_quality = self.audio_bitrate_mapping.get(audio_quality_display, "best") if hasattr(self, 'audio_bitrate_mapping') else "best"

        sponsorblock_enabled = self.sponsorblock_enabled.get() if hasattr(self, 'sponsorblock_enabled') else False
        sponsorblock_mode = self.sponsorblock_mode_var.get() if hasattr(self, 'sponsorblock_mode_var') else "mark"
        sponsorblock_categories = []
        if sponsorblock_enabled and hasattr(self, 'sponsorblock_categories'):
            sponsorblock_categories = [
                key for key, var in self.sponsorblock_categories.items() if var.get()
            ]
            if not sponsorblock_categories:
                messagebox.showerror("SponsorBlock", "Please select at least one category to block.")
                return None

        return {
            "format_type": format_type,
            "quality": quality,
            "trim_start": trim_start,
            "trim_end": trim_end,
            "mode": mode,
            "convert_enabled": convert_enabled,
            "convert_format": convert_format,
            "audio_quality": audio_quality,
            "save_thumbnail_file": save_thumbnail_file,
            "save_subtitles": save_subtitles,
            "embed_chapters": embed_chapters,
            "keep_original_file": keep_original_file,
            "write_description": write_description,
            "skip_existing": skip_existing,
            "allow_duplicates": allow_duplicates,
            "output_template": output_template,
            "sponsorblock_enabled": sponsorblock_enabled,
            "sponsorblock_mode": sponsorblock_mode,
            "sponsorblock_categories": sponsorblock_categories,
        }

    def _start_queue_download(self):
        """Download all queued URLs using current download settings."""
        if self.is_queue_downloading:
            messagebox.showwarning("Queue", "Queue download is already running.")
            return
        if not self.url_queue:
            messagebox.showwarning("Queue", "Queue is empty.")
            return
        if not self.validate_inputs(url_override=self.url_queue[0].get("url", "")):
            return

        settings = self._collect_download_settings()
        if not settings:
            return

        queued_items = list(self.url_queue)
        self.is_queue_downloading = True

        self.download_btn.configure(state='disabled')
        self.cancel_btn.configure(state='normal')
        self.status_var.set("Downloading queue...")
        self.download_progress_frame.grid()
        self.download_progress_bar.set(0)
        self.download_progress_label.configure(text=f"Preparing queue ({len(queued_items)} items)...")
        self.tabview.set("📄 Output Log")

        self.output_text.configure(state='normal')
        self.output_text.delete(1.0, tk.END)
        self.output_text.configure(state='disabled')

        yt_dlp_path = self.yt_dlp_entry.get().strip()
        output_dir = self.output_entry.get().strip()
        ffmpeg_path = self._find_ffmpeg_path()

        def queue_thread():
            download_event = threading.Event()
            last_error = [None]
            total = len(queued_items)

            def on_video_complete():
                download_event.set()

            def on_video_error(error_msg):
                last_error[0] = error_msg
                download_event.set()

            for idx, item in enumerate(queued_items, 1):
                url = item.get("url", "")
                title = item.get("title", url)

                self.log_message(f"\n{'='*70}")
                self.log_message(f"Queue item {idx}/{total}: {title}")
                self.log_message(f"{'='*70}")
                self.download_progress_bar.set((idx - 1) / total)
                self.download_progress_label.configure(text=f"Downloading {idx}/{total}: {title[:50]}...")

                download_event.clear()
                last_error[0] = None

                self.downloader.download(
                    yt_dlp_path=yt_dlp_path,
                    url=url,
                    output_dir=output_dir,
                    format_type=settings["format_type"],
                    quality=settings["quality"],
                    trim_start=settings["trim_start"],
                    trim_end=settings["trim_end"],
                    audio_quality=settings["audio_quality"],
                    on_log=self.log_message,
                    on_complete=on_video_complete,
                    on_error=on_video_error,
                    on_download_started=self._on_download_started,
                    on_progress=self._on_download_progress,
                    mode=settings["mode"],
                    is_playlist_item=True,
                    convert_enabled=settings["convert_enabled"],
                    convert_format=settings["convert_format"],
                    save_thumbnail_file=settings["save_thumbnail_file"],
                    save_subtitles=settings["save_subtitles"],
                    embed_chapters=settings["embed_chapters"],
                    keep_original_file=settings["keep_original_file"],
                    write_description=settings["write_description"],
                    skip_existing=settings["skip_existing"],
                    allow_duplicates=settings["allow_duplicates"],
                    output_template=settings["output_template"],
                    sponsorblock_enabled=settings["sponsorblock_enabled"],
                    sponsorblock_mode=settings["sponsorblock_mode"],
                    sponsorblock_categories=settings["sponsorblock_categories"],
                    ffmpeg_path=ffmpeg_path
                )
                download_event.wait()

                if last_error[0]:
                    break

                self._remember_recent_url(url, title=title, platform=self._get_platform_from_url(url))

            self.is_queue_downloading = False

            if last_error[0]:
                self.status_var.set("Queue download failed")
                self.download_progress_label.configure(text="✗ Queue failed")
                formatted = self._format_error_for_dialog(last_error[0])
                self.root.after(0, lambda msg=formatted: messagebox.showerror("Queue Error", msg))
            else:
                self.url_queue = []
                self._refresh_queue_ui()
                self.status_var.set("Queue download complete")
                self.download_progress_bar.set(1.0)
                self.download_progress_label.configure(text="✓ Queue download completed!")
                self._perform_after_download_action()
                self.root.after(0, lambda: messagebox.showinfo("Queue Complete", "All queued downloads completed."))

            self.download_btn.configure(state='normal')
            self.cancel_btn.configure(state='disabled')
            self.root.after(2000, self.download_progress_frame.grid_remove)

        threading.Thread(target=queue_thread, daemon=True).start()

    def _translate_error_message(self, error_msg: str) -> str:
        """Convert raw yt-dlp/ffmpeg errors into friendlier guidance."""
        text = (error_msg or "").strip()
        lower = text.lower()

        if "429" in lower or "too many requests" in lower or "rate limit" in lower:
            return "The site rate-limited this request. Try again in a few minutes."
        if "unsupported url" in lower or "unsupported" in lower and "url" in lower:
            return "This URL is not supported by the current yt-dlp build."
        if "ffmpeg" in lower and ("not found" in lower or "not installed" in lower):
            return "FFmpeg is missing. Install FFmpeg and try again."
        if "private" in lower or "login" in lower or "sign in" in lower:
            return "This media requires authentication or is private."
        if "timed out" in lower or "timeout" in lower:
            return "The request timed out. Check your connection and retry."
        if "unable to extract" in lower:
            return "The site likely changed. Update yt-dlp and retry."
        if "noneType.__format__".lower() in lower:
            return "Some metadata fields were missing unexpectedly. Please retry."
        return text

    def _format_error_for_dialog(self, raw_error: str) -> str:
        """Build user-facing error text with optional technical details."""
        technical = (raw_error or "").strip() or "Unknown error"
        friendly = self._translate_error_message(technical)
        if friendly and friendly != technical:
            return f"{friendly}\n\nTechnical details:\n{technical}"
        return technical

    def _perform_after_download_action(self):
        """Run post-download action selected by the user."""
        action = self.after_download_var.get().strip() if hasattr(self, 'after_download_var') else "Do nothing"
        output_dir = self.output_entry.get().strip()
        target_path = self.downloader.last_downloaded_file or output_dir

        if action == "Open folder":
            try:
                if os.name == 'nt':
                    os.startfile(output_dir)  # type: ignore[attr-defined]
                elif os.name == 'posix':
                    subprocess.Popen(["xdg-open", output_dir])
                self.log_message("Opened output folder")
            except Exception as e:
                self.log_message(f"⚠ Could not open output folder: {str(e)}")
        elif action == "Copy file path":
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(target_path)
                self.root.update()
                self.log_message(f"Copied path: {target_path}")
            except Exception as e:
                self.log_message(f"⚠ Could not copy path: {str(e)}")

    def _find_ffmpeg_path(self):
        """Best-effort FFmpeg path detection."""
        try:
            saved_path = self.config.get('ffmpeg_path', '') if hasattr(self, "config") else ''
            if saved_path and os.path.exists(saved_path):
                return saved_path
        except Exception:
            pass

        from_path = shutil.which("ffmpeg")
        if from_path:
            return from_path

        yt_dlp_path = self.yt_dlp_entry.get().strip()
        if yt_dlp_path:
            local_candidate = os.path.join(os.path.dirname(yt_dlp_path), "ffmpeg.exe")
            if os.path.exists(local_candidate):
                return local_candidate

        return ""

    def _refresh_tool_status(self):
        """Refresh yt-dlp / FFmpeg availability badges."""
        if hasattr(self, "ytdlp_status_label"):
            yt_dlp_path = self.yt_dlp_entry.get().strip()
            if yt_dlp_path and os.path.exists(yt_dlp_path):
                self.ytdlp_status_label.configure(text="yt-dlp: Ready", text_color=("#2e7d32", "#81c784"))
            else:
                self.ytdlp_status_label.configure(text="yt-dlp: Missing", text_color=("#c62828", "#ef9a9a"))

        if hasattr(self, "ffmpeg_status_label"):
            ffmpeg_path = self._find_ffmpeg_path()
            if ffmpeg_path:
                self.ffmpeg_status_label.configure(text="FFmpeg: Ready", text_color=("#2e7d32", "#81c784"))
            else:
                self.ffmpeg_status_label.configure(text="FFmpeg: Missing", text_color=("#c62828", "#ef9a9a"))

    def _update_ytdlp_binary(self):
        """Run in-place yt-dlp self-update using the configured executable."""
        yt_dlp_path = self.yt_dlp_entry.get().strip()
        if not yt_dlp_path or not os.path.exists(yt_dlp_path):
            messagebox.showerror("Update yt-dlp", "Please select a valid yt-dlp executable first.")
            return

        self.tabview.set("📄 Output Log")
        self.log_message(f"Updating yt-dlp: {yt_dlp_path}")
        self.log_message("-" * 70)

        def update_thread():
            try:
                process = subprocess.Popen(
                    [yt_dlp_path, "-U"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                for line in process.stdout:
                    self.log_message(line.rstrip())
                process.wait()
                if process.returncode == 0:
                    self.log_message("✓ yt-dlp update finished")
                else:
                    self.log_message(f"✗ yt-dlp update failed with code {process.returncode}")
            except Exception as e:
                self.log_message(f"✗ yt-dlp update error: {str(e)}")
            finally:
                self.root.after(0, self._refresh_tool_status)

        threading.Thread(target=update_thread, daemon=True).start()

    def _list_supported_sites(self):
        """List all supported yt-dlp extractors/sites in output log."""
        yt_dlp_path = self.yt_dlp_entry.get().strip()
        if not yt_dlp_path or not os.path.exists(yt_dlp_path):
            messagebox.showerror("Supported Sites", "Please select a valid yt-dlp executable first.")
            return

        self.tabview.set("📄 Output Log")
        self.log_message(f"Listing supported sites: {yt_dlp_path}")
        self.log_message("Command: --list-extractors")
        self.log_message("-" * 70)

        def list_thread():
            count = 0
            try:
                process = subprocess.Popen(
                    [yt_dlp_path, "--list-extractors"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                for line in process.stdout:
                    text = line.rstrip()
                    if text:
                        count += 1
                        self.log_message(text)

                process.wait()
                self.log_message("-" * 70)
                if process.returncode == 0:
                    self.log_message(f"✓ Extractors listed: {count}")
                else:
                    self.log_message(f"✗ Failed to list extractors (code {process.returncode})")
            except Exception as e:
                self.log_message(f"✗ Error listing extractors: {str(e)}")

        threading.Thread(target=list_thread, daemon=True).start()

    def _sanitize_filename_component(self, value: str) -> str:
        """Sanitize title for filesystem-safe preview."""
        cleaned = re.sub(r'[<>:"/\\|?*]+', '', value or "").strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned[:120] if cleaned else "video"

    def _get_filename_style(self) -> str:
        """Get selected filename style."""
        if hasattr(self, "filename_style_var"):
            try:
                style = (self.filename_style_var.get() or "classic").strip().lower()
                if style in ["classic", "basic", "pretty", "nerdy"]:
                    return style
            except Exception:
                pass
        return "classic"

    def _normalize_upload_date(self, value: str) -> str:
        """Convert YYYYMMDD to YYYY-MM-DD for display."""
        raw = (value or "").strip()
        if len(raw) == 8 and raw.isdigit():
            return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
        return raw or "date"

    def _get_current_mode(self) -> str:
        """Get current mode value used by the app."""
        if hasattr(self, "mode_var"):
            try:
                return (self.mode_var.get() or "video_audio").strip().lower()
            except Exception:
                pass
        return "video_audio"

    def _normalize_resolution_label(self, value: str, height=None) -> str:
        """Normalize resolution text for preview display."""
        try:
            if height is not None and str(height).isdigit():
                return f"{int(height)}p"
        except Exception:
            pass
        raw = (value or "").strip()
        match = re.match(r"^\d+x(\d+)$", raw, re.IGNORECASE)
        if match:
            return f"{match.group(1)}p"
        if raw.isdigit():
            return f"{raw}p"
        return raw or "1080p"

    def _normalize_codec_label(self, value: str) -> str:
        """Normalize codec text for preview display."""
        raw = (value or "").strip().lower()
        if not raw or raw == "none":
            return "h264"
        if raw.startswith("avc") or raw.startswith("h264"):
            return "h264"
        if raw.startswith("hev") or raw.startswith("hvc") or raw.startswith("h265"):
            return "h265"
        if raw.startswith("vp9"):
            return "vp9"
        if raw.startswith("av01") or raw.startswith("av1"):
            return "av1"
        return raw.split(".")[0]

    def _build_output_template(self, output_dir: str) -> str:
        """Build yt-dlp output template path from selected filename style."""
        style = self._get_filename_style()
        mode = self._get_current_mode()
        audio_templates = {
            "classic": "%(extractor)s_%(id)s.%(ext)s",
            "pretty": "%(title)s - %(uploader)s.%(ext)s",
            "basic": "%(title)s - %(uploader)s (%(extractor)s).%(ext)s",
            "nerdy": "%(title)s - %(uploader)s (%(extractor)s, %(id)s).%(ext)s",
        }
        video_templates = {
            "classic": "%(extractor)s_%(id)s.%(ext)s",
            "pretty": "%(title)s (%(resolution)s, %(vcodec)s).%(ext)s",
            "basic": "%(title)s (%(resolution)s, %(vcodec)s, %(extractor)s).%(ext)s",
            "nerdy": "%(title)s (%(resolution)s, %(vcodec)s, %(extractor)s, %(id)s).%(ext)s",
        }
        templates = audio_templates if mode == "audio" else video_templates
        filename_template = templates.get(style, templates["classic"])
        return os.path.join(output_dir, filename_template)

    def _guess_output_extension(self) -> str:
        """Guess extension based on current controls."""
        if hasattr(self, "convert_enabled") and hasattr(self, "convert_format_var"):
            try:
                if self.convert_enabled.get() and self.convert_format_var.get().strip():
                    return self.convert_format_var.get().strip().lower()
            except Exception:
                pass

        fmt = ""
        if hasattr(self, "format_var"):
            try:
                fmt = (self.format_var.get() or "").strip().lower()
            except Exception:
                fmt = ""
        if fmt:
            return fmt

        mode = "video_audio"
        if hasattr(self, "mode_var"):
            try:
                mode = self.mode_var.get()
            except Exception:
                mode = "video_audio"
        return "mp3" if mode == "audio" else "mp4"

    def _update_filename_preview(self):
        """Update output filename preview label."""
        if not hasattr(self, "filename_preview_var"):
            return

        title = "video"
        uploader = "uploader"
        extractor = self._get_platform_from_url(self.url_entry.get().strip()) if hasattr(self, "url_entry") else "site"
        media_id = "id"
        resolution = "1080p"
        codec = "h264"
        if isinstance(self.current_metadata, dict):
            title = self.current_metadata.get("title", "") or title
            uploader = self.current_metadata.get("uploader", "") or uploader
            extractor = (
                self.current_metadata.get("extractor", "")
                or self.current_metadata.get("extractor_key", "")
                or extractor
            )
            media_id = self.current_metadata.get("id", "") or media_id
            resolution = self._normalize_resolution_label(
                self.current_metadata.get("resolution", ""),
                self.current_metadata.get("height", None),
            )
            codec = self._normalize_codec_label(self.current_metadata.get("vcodec", ""))

        style = self._get_filename_style()
        mode = self._get_current_mode()
        preview_base = f"{extractor}_{media_id}"
        if mode == "audio":
            if style == "pretty":
                preview_base = f"{title} - {uploader}"
            elif style == "basic":
                preview_base = f"{title} - {uploader} ({extractor})"
            elif style == "nerdy":
                preview_base = f"{title} - {uploader} ({extractor}, {media_id})"
        else:
            if style == "pretty":
                preview_base = f"{title} ({resolution}, {codec})"
            elif style == "basic":
                preview_base = f"{title} ({resolution}, {codec}, {extractor})"
            elif style == "nerdy":
                preview_base = f"{title} ({resolution}, {codec}, {extractor}, {media_id})"

        safe_title = self._sanitize_filename_component(preview_base)
        ext = self._guess_output_extension()
        output_dir = self.output_entry.get().strip() or str(Path.home() / "Downloads")
        preview_path = os.path.join(output_dir, f"{safe_title}.{ext}")
        self.filename_preview_var.set(f"Preview: {preview_path}")

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
            self._refresh_tool_status()
    
    def browse_output(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, directory)
            self.config.set('output_dir', directory)
            self._update_filename_preview()

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
            self._on_url_changed()
            if self.auto_fetch_on_paste and self.is_valid_url(clipboard_text.strip()) and self.yt_dlp_entry.get().strip():
                self.fetch_video_info()
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
        self._remember_recent_url(url)
        self._update_filename_preview()

        # Fetch metadata
        self.metadata_fetcher.fetch_metadata(
            yt_dlp_path=yt_dlp_path,
            url=url,
            on_success=self._on_metadata_success,
            on_error=self._on_metadata_error,
            on_log=self.log_message
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

        if self.quick_preset_active:
            self._reapply_active_quick_preset()

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
        self._update_filename_preview()

        current_url = self.url_entry.get().strip()
        if current_url:
            self._remember_recent_url(
                current_url,
                title=metadata.get('title', current_url),
                platform=self._get_platform_from_url(current_url)
            )

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
        formatted_error = self._format_error_for_dialog(error_msg)
        self.log_message(f"✗ Error: {formatted_error}")
        messagebox.showerror("Fetch Error", f"Failed to fetch video information:\n{formatted_error}")
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
            self._update_filename_preview()

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
            self._update_filename_preview()

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
        self._update_filename_preview()

    # Playlist handling occurs automatically after fetch when a playlist URL is detected.

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

    def _copy_log(self):
        """Copy all log text to clipboard."""
        try:
            text = self.output_text.get("1.0", tk.END).strip()
            if not text:
                messagebox.showinfo("Copy Log", "Log is empty.")
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            messagebox.showinfo("Copy Log", "Log copied to clipboard.")
        except tk.TclError:
            messagebox.showerror("Copy Log", "Failed to copy log.")

    def _clear_log(self):
        """Clear output log."""
        try:
            self.output_text.configure(state='normal')
            self.output_text.delete("1.0", tk.END)
            self.output_text.configure(state='disabled')
        except tk.TclError:
            messagebox.showerror("Clear Log", "Failed to clear log.")

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

    def validate_inputs(self, url_override: str = ""):
        """
        Validate user inputs before download
        
        Returns:
            True if all inputs are valid, False otherwise
        """
        yt_dlp_path = self.yt_dlp_entry.get().strip()
        url = url_override.strip() if url_override else self.url_entry.get().strip()
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
            self._remember_recent_url(self.url_entry.get().strip())
            self._update_filename_preview()
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
        settings = self._collect_download_settings()
        if not settings:
            self.download_btn.configure(state='normal')
            self.cancel_btn.configure(state='disabled')
            self.status_var.set("Ready")
            return

        ffmpeg_path = self._find_ffmpeg_path()

        self._remember_recent_url(url)
        self._update_filename_preview()

        # Check if this is a playlist download
        if self.current_metadata.get('is_playlist', False):
            selected_videos = self.current_metadata.get('selected_videos', [])
            self._start_playlist_download(
                yt_dlp_path=yt_dlp_path,
                selected_videos=selected_videos,
                output_dir=output_dir,
                format_type=settings["format_type"],
                quality=settings["quality"],
                trim_start=settings["trim_start"],
                trim_end=settings["trim_end"],
                mode=settings["mode"],
                audio_quality=settings["audio_quality"],
                convert_enabled=settings["convert_enabled"],
                convert_format=settings["convert_format"],
                save_thumbnail_file=settings["save_thumbnail_file"],
                save_subtitles=settings["save_subtitles"],
                embed_chapters=settings["embed_chapters"],
                keep_original_file=settings["keep_original_file"],
                write_description=settings["write_description"],
                skip_existing=settings["skip_existing"],
                allow_duplicates=settings["allow_duplicates"],
                output_template=settings["output_template"],
                sponsorblock_enabled=settings["sponsorblock_enabled"],
                sponsorblock_mode=settings["sponsorblock_mode"],
                sponsorblock_categories=settings["sponsorblock_categories"],
                ffmpeg_path=ffmpeg_path
            )
            return

        # Start download
        self.downloader.download(
            yt_dlp_path=yt_dlp_path,
            url=url,
            output_dir=output_dir,
            format_type=settings["format_type"],
            quality=settings["quality"],
            trim_start=settings["trim_start"],
            trim_end=settings["trim_end"],
            audio_quality=settings["audio_quality"],
            on_log=self.log_message,
            on_complete=self._on_download_complete,
            on_error=self._on_download_error,
            on_download_started=self._on_download_started,
            on_progress=self._on_download_progress,
            mode=settings["mode"],
            convert_enabled=settings["convert_enabled"],
            convert_format=settings["convert_format"],
            save_thumbnail_file=settings["save_thumbnail_file"],
            save_subtitles=settings["save_subtitles"],
            embed_chapters=settings["embed_chapters"],
            keep_original_file=settings["keep_original_file"],
            write_description=settings["write_description"],
            skip_existing=settings["skip_existing"],
            allow_duplicates=settings["allow_duplicates"],
            output_template=settings["output_template"],
            sponsorblock_enabled=settings["sponsorblock_enabled"],
            sponsorblock_mode=settings["sponsorblock_mode"],
            sponsorblock_categories=settings["sponsorblock_categories"],
            ffmpeg_path=ffmpeg_path
        )

    def _start_playlist_download(self, yt_dlp_path, selected_videos, output_dir, format_type, quality, trim_start, trim_end, mode, audio_quality="best", convert_enabled=False, convert_format="", save_thumbnail_file=False, save_subtitles=False, embed_chapters=False, keep_original_file=False, write_description=False, skip_existing=False, allow_duplicates=False, output_template=None, sponsorblock_enabled=False, sponsorblock_mode="mark", sponsorblock_categories=None, ffmpeg_path=None):
        """Start downloading multiple videos from a playlist"""
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
                    audio_quality=audio_quality,
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
                    embed_chapters=embed_chapters,
                    keep_original_file=keep_original_file,
                    write_description=write_description,
                    skip_existing=skip_existing,
                    allow_duplicates=allow_duplicates,
                    output_template=output_template,
                    sponsorblock_enabled=sponsorblock_enabled,
                    sponsorblock_mode=sponsorblock_mode,
                    sponsorblock_categories=sponsorblock_categories,
                    ffmpeg_path=ffmpeg_path
                )

                # Wait for this video to complete
                download_event.wait()

                # If error occurred, stop downloading
                if download_error[0]:
                    self.log_message(f"\n✗ Error downloading video {idx}, stopping playlist download")
                    break

                self._remember_recent_url(video_url)

            # All videos downloaded
            self.download_progress_bar.set(1.0)
            self.download_progress_label.configure(text=f"Completed downloading {total_videos} videos")
            self.log_message(f"\n{'='*70}")
            self.log_message(f"✓ Playlist download complete! Downloaded {total_videos} videos")
            self.log_message(f"{'='*70}")
            self._perform_after_download_action()

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
        output_template = self._build_output_template(output_dir)

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
        self._perform_after_download_action()

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

        formatted_error = self._format_error_for_dialog(error_msg)
        messagebox.showerror("Error", f"Download failed:\n{formatted_error}")

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

