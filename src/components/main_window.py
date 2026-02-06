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

class TimeEntry(ctk.CTkFrame):
    """Custom time entry widget (HH:MM:SS) with up/down arrow support and backspace/del reset to 0."""

    def __init__(self, master, width=120, state='normal', **kwargs):
        super().__init__(master, fg_color="transparent")
        self._time_var = tk.StringVar(value="00:00:00")
        self._state = state
        self._entry = ctk.CTkEntry(self, width=width, font=('Arial', 12),
                                   textvariable=self._time_var, justify='center')
        self._entry.pack(fill=tk.X)

        # Bind events on the internal tk entry for reliable key handling
        internal = self._entry._entry
        internal.bind("<KeyPress>", self._on_key_press)
        internal.bind("<Up>", self._on_arrow_up)
        internal.bind("<Down>", self._on_arrow_down)

        if state == 'disabled':
            self._entry.configure(state='disabled')

    def _get_cursor_segment(self):
        """Return which segment (0=hours, 1=minutes, 2=seconds) the cursor is in."""
        try:
            pos = self._entry._entry.index(tk.INSERT)
        except Exception:
            pos = 0
        if pos <= 2:
            return 0
        elif pos <= 5:
            return 1
        else:
            return 2

    def _parse_time(self):
        """Parse current value into [h, m, s]."""
        val = self._time_var.get()
        try:
            parts = val.split(':')
            return [int(parts[0]), int(parts[1]), int(parts[2])]
        except Exception:
            return [0, 0, 0]

    def _format_time(self, h, m, s):
        """Format h, m, s into HH:MM:SS string."""
        h = max(0, min(h, 99))
        m = max(0, min(m, 59))
        s = max(0, min(s, 59))
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _set_time(self, h, m, s):
        """Set the time value and restore cursor position."""
        try:
            pos = self._entry._entry.index(tk.INSERT)
        except Exception:
            pos = 0
        self._time_var.set(self._format_time(h, m, s))
        try:
            self._entry._entry.icursor(pos)
        except Exception:
            pass

    def _on_key_press(self, event):
        """Handle key presses: digits replace at cursor, backspace/del reset to 0."""
        if self._state == 'disabled':
            return "break"

        # Allow navigation keys
        if event.keysym in ('Left', 'Right', 'Home', 'End', 'Tab', 'Shift_L', 'Shift_R'):
            return None

        # Up/Down handled separately
        if event.keysym in ('Up', 'Down'):
            return None

        val = self._time_var.get()
        try:
            pos = self._entry._entry.index(tk.INSERT)
        except Exception:
            pos = 0

        if event.keysym in ('BackSpace', 'Delete'):
            # Reset digit at cursor position to 0
            if event.keysym == 'BackSpace' and pos > 0:
                target = pos - 1
            else:
                target = pos
            # Skip colons
            if target < len(val) and val[target] == ':':
                return "break"
            if 0 <= target < len(val) and val[target] != ':':
                new_val = val[:target] + '0' + val[target + 1:]
                self._time_var.set(new_val)
                self._entry._entry.icursor(target if event.keysym == 'BackSpace' else target + 1)
            return "break"

        if event.char and event.char.isdigit():
            # Skip colon positions
            if pos < len(val) and val[pos] == ':':
                pos += 1
            if pos < len(val) and val[pos] != ':':
                new_val = val[:pos] + event.char + val[pos + 1:]
                # Validate segments
                try:
                    parts = new_val.split(':')
                    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
                    if m > 59 or s > 59 or h > 99:
                        return "break"
                except Exception:
                    return "break"
                self._time_var.set(new_val)
                # Move cursor forward, skip colons
                new_pos = pos + 1
                if new_pos < len(new_val) and new_val[new_pos] == ':':
                    new_pos += 1
                self._entry._entry.icursor(new_pos)
            return "break"

        # Block all other input
        return "break"

    def _on_arrow_up(self, event):
        """Increment the segment at cursor by 1."""
        if self._state == 'disabled':
            return "break"
        seg = self._get_cursor_segment()
        h, m, s = self._parse_time()
        if seg == 0:
            h = min(h + 1, 99)
        elif seg == 1:
            m = min(m + 1, 59)
        else:
            s = min(s + 1, 59)
        self._set_time(h, m, s)
        return "break"

    def _on_arrow_down(self, event):
        """Decrement the segment at cursor by 1."""
        if self._state == 'disabled':
            return "break"
        seg = self._get_cursor_segment()
        h, m, s = self._parse_time()
        if seg == 0:
            h = max(h - 1, 0)
        elif seg == 1:
            m = max(m - 1, 0)
        else:
            s = max(s - 1, 0)
        self._set_time(h, m, s)
        return "break"

    def get(self):
        """Get the current time string."""
        return self._time_var.get().strip()

    def delete(self, start, end):
        """Reset to 00:00:00."""
        self._time_var.set("00:00:00")

    def insert(self, index, value):
        """Set the time value (expects HH:MM:SS format)."""
        # Validate and set
        try:
            parts = value.strip().split(':')
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
            self._time_var.set(self._format_time(h, m, s))
        except Exception:
            self._time_var.set(value)

    def configure(self, **kwargs):
        """Configure the widget."""
        if 'state' in kwargs:
            self._state = kwargs['state']
            self._entry.configure(state=kwargs['state'])
            del kwargs['state']
        if kwargs:
            super().configure(**kwargs)

    def select_range(self, start, end):
        """Select a range of text."""
        self._entry.select_range(start, end)


from ..config import ConfigManager
from ..downloader import Downloader
from ..metadata import MetadataFetcher
from ..ytdlp_manager import YtdlpDownloader
from ..ffmpeg_manager import FFmpegDownloader
from ..templates import TemplateManager
from .context_menu import ContextMenu
from .playlist_selector import PlaylistSelector


class MainWindow:
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

        # Load saved yt-dlp path
        saved_path = self.config.get('yt_dlp_path', '')
        if saved_path:
            self.yt_dlp_entry.insert(0, saved_path)

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

    def _configure_styles(self):
        """Configure custom styles for the application"""
        # Configure colors (for reference, though customtkinter handles most styling)
        self.colors = {
            'primary': '#2196F3',      # Blue
            'success': '#4CAF50',      # Green
            'warning': '#FF9800',      # Orange
            'error': '#F44336',        # Red
            'bg_light': '#F5F5F5',     # Light gray
            'text_dark': '#212121',    # Dark gray
            'text_light': '#757575'    # Medium gray
        }

    def create_widgets(self):
        """Create and layout all GUI widgets"""
        # Main container with minimal padding
        main_frame = ctk.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Configure grid weights for responsiveness
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        # yt-dlp Path Section (always visible at top)
        self._create_ytdlp_section(main_frame)

        # Create tabview (tabbed interface)
        self.tabview = ctk.CTkTabview(main_frame)
        self.tabview.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))

        # Create tabs
        self.download_tab = self.tabview.add("📥 Download")
        self.ytdlp_tab = self.tabview.add("⚙️ Get yt-dlp")
        self.ffmpeg_tab = self.tabview.add("🎬 Get FFmpeg")
        self.templates_tab = self.tabview.add("📋 Templates")
        self.log_tab = self.tabview.add("📄 Output Log")

        # Configure tab weights
        self.download_tab.columnconfigure(0, weight=1)
        self.ytdlp_tab.columnconfigure(0, weight=1)
        self.ffmpeg_tab.columnconfigure(0, weight=1)
        self.templates_tab.columnconfigure(0, weight=1)
        self.log_tab.columnconfigure(0, weight=1)
        self.log_tab.rowconfigure(0, weight=1)

        # Create scrollable frame for download tab
        self.download_scrollable = ctk.CTkScrollableFrame(self.download_tab)
        self.download_scrollable.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.download_scrollable.columnconfigure(0, weight=1)

        # Track if scrollbar is shown (for compatibility)
        self.scrollbar_visible = False

        # Populate Download Tab
        self._create_download_tab_content()

        # Populate Get yt-dlp Tab
        self._create_ytdlp_tab_content()

        # Populate Get FFmpeg Tab
        self._create_ffmpeg_tab_content()

        # Populate Templates Tab
        self._create_templates_tab_content()

        # Populate Log Tab
        self._create_log_tab_content()

        # Status Bar (always visible at bottom)
        self._create_status_bar(main_frame)

    def _create_download_tab_content(self):
        """Create content for download tab"""
        # Video URL Section
        self._create_url_section(self.download_scrollable)

        # Video Metadata Section
        self._create_metadata_section(self.download_scrollable)

        # Trim/Cut Section
        self._create_trim_section(self.download_scrollable)

        # Output Directory Section
        self._create_output_section(self.download_scrollable)

        # Format Selection Section (Download Options)
        self._create_format_section(self.download_scrollable)

        # Convert To Section (after Download Options)
        self._create_convert_section(self.download_scrollable)

        # Quality Selection Section
        self._create_quality_section(self.download_scrollable)

        # Download Button
        self._create_download_button(self.download_scrollable)

    def _create_log_tab_content(self):
        """Create content for log tab"""
        # Output log
        self._create_output_log(self.log_tab)

    def _create_ytdlp_tab_content(self):
        """Create content for Get yt-dlp tab"""
        # Title
        ctk.CTkLabel(self.ytdlp_tab, text="Download yt-dlp Executable",
                 font=('Arial', 14, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Description
        desc_text = "Download the latest yt-dlp executable directly from GitHub.\nChoose between Stable, Nightly, or Master builds."
        ctk.CTkLabel(self.ytdlp_tab, text=desc_text, font=('Arial', 12)).grid(
            row=1, column=0, sticky=tk.W, pady=(0, 15))

        # Version selection
        version_frame = ctk.CTkFrame(self.ytdlp_tab)
        version_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10), padx=10)
        version_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(version_frame, text="Select Version", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(5, 5), padx=10)

        self.ytdlp_version_var = tk.StringVar(value="stable")

        ctk.CTkRadioButton(version_frame, text="Stable - Recommended for most users",
                       variable=self.ytdlp_version_var, value="stable").grid(
            row=1, column=0, sticky=tk.W, pady=2, padx=10)

        ctk.CTkRadioButton(version_frame, text="Nightly - Latest features and fixes",
                       variable=self.ytdlp_version_var, value="nightly").grid(
            row=2, column=0, sticky=tk.W, pady=2, padx=10)

        ctk.CTkRadioButton(version_frame, text="Master - Bleeding edge (may be unstable)",
                       variable=self.ytdlp_version_var, value="master").grid(
            row=3, column=0, sticky=tk.W, pady=(2, 10), padx=10)

        # Output location
        location_frame = ctk.CTkFrame(self.ytdlp_tab)
        location_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10), padx=10)
        location_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(location_frame, text="Save Location", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(5, 5), padx=10)

        self.ytdlp_save_entry = ctk.CTkEntry(location_frame, width=50)
        self.ytdlp_save_entry.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=(10, 5), pady=(0, 10))
        default_path = str(Path.home() / "Downloads" / "yt-dlp.exe")
        self.ytdlp_save_entry.insert(0, default_path)
        # Add context menu
        ContextMenu(self.ytdlp_save_entry)

        ctk.CTkButton(location_frame, text="📁 Browse...",
                  command=self._browse_ytdlp_save_location).grid(row=1, column=1, padx=(0, 10), pady=(0, 10))

        # Progress bar
        self.ytdlp_progress_frame = ctk.CTkFrame(self.ytdlp_tab)
        self.ytdlp_progress_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        self.ytdlp_progress_frame.columnconfigure(0, weight=1)

        self.ytdlp_progress_label = ctk.CTkLabel(self.ytdlp_progress_frame, text="",
                                             font=('Arial', 12))
        self.ytdlp_progress_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        self.ytdlp_progress_bar = ctk.CTkProgressBar(self.ytdlp_progress_frame,
                                                  mode='determinate')
        self.ytdlp_progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.ytdlp_progress_bar.set(0)

        # Initially hide progress
        self.ytdlp_progress_frame.grid_remove()

        # Download button
        self.ytdlp_download_btn = ctk.CTkButton(self.ytdlp_tab, text="📥 Download yt-dlp",
                                            command=self._download_ytdlp)
        self.ytdlp_download_btn.grid(row=5, column=0, pady=(0, 10), sticky=(tk.W, tk.E))

        # Info text
        info_text = ("After downloading, the path will be automatically set in the main tab.\n"
                    "You can also manually browse for an existing yt-dlp.exe file.")
        ctk.CTkLabel(self.ytdlp_tab, text=info_text, font=('Arial', 11),
                 text_color='gray').grid(row=6, column=0, sticky=tk.W)

    def _create_ffmpeg_tab_content(self):
        """Create content for Get FFmpeg tab"""
        # Title
        ctk.CTkLabel(self.ffmpeg_tab, text="Download FFmpeg Executable",
                 font=('Arial', 14, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Description
        desc_text = "Download the latest FFmpeg executable directly from GitHub.\nFFmpeg is required for advanced video processing."
        ctk.CTkLabel(self.ffmpeg_tab, text=desc_text, font=('Arial', 12)).grid(
            row=1, column=0, sticky=tk.W, pady=(0, 15))

        # Output location
        location_frame = ctk.CTkFrame(self.ffmpeg_tab)
        location_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10), padx=10)
        location_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(location_frame, text="Save Location", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(5, 5), padx=10)

        self.ffmpeg_save_entry = ctk.CTkEntry(location_frame, width=50)
        self.ffmpeg_save_entry.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=(10, 5), pady=(0, 10))
        default_path = str(Path.home() / "Downloads" / "ffmpeg.exe")
        self.ffmpeg_save_entry.insert(0, default_path)
        # Add context menu
        ContextMenu(self.ffmpeg_save_entry)

        ctk.CTkButton(location_frame, text="📁 Browse...",
                  command=self._browse_ffmpeg_save_location).grid(row=1, column=1, padx=(0, 10), pady=(0, 10))

        # Progress bar
        self.ffmpeg_progress_frame = ctk.CTkFrame(self.ffmpeg_tab)
        self.ffmpeg_progress_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        self.ffmpeg_progress_frame.columnconfigure(0, weight=1)

        self.ffmpeg_progress_label = ctk.CTkLabel(self.ffmpeg_progress_frame, text="",
                                              font=('Arial', 12))
        self.ffmpeg_progress_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        self.ffmpeg_progress_bar = ctk.CTkProgressBar(self.ffmpeg_progress_frame,
                                                   mode='determinate')
        self.ffmpeg_progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.ffmpeg_progress_bar.set(0)

        # Initially hide progress
        self.ffmpeg_progress_frame.grid_remove()

        # Download button
        self.ffmpeg_download_btn = ctk.CTkButton(self.ffmpeg_tab, text="📥 Download FFmpeg",
                                             command=self._download_ffmpeg)
        self.ffmpeg_download_btn.grid(row=4, column=0, pady=(0, 10), sticky=(tk.W, tk.E))

        # Info text
        info_text = ("After downloading, you can use FFmpeg for advanced video processing.\n"
                    "If you already have FFmpeg, it will be automatically detected.")
        ctk.CTkLabel(self.ffmpeg_tab, text=info_text, font=('Arial', 11),
                 text_color='gray').grid(row=5, column=0, sticky=tk.W)

    def _create_templates_tab_content(self):
        """Create content for Templates tab"""
        # Configure templates tab grid weights
        self.templates_tab.rowconfigure(2, weight=1)  # Make content frame expand

        # Title and description
        header_frame = ctk.CTkFrame(self.templates_tab)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 1))
        header_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="Custom yt-dlp Command Templates",
                 font=('Arial', 12, 'bold')).grid(row=0, column=0, sticky=tk.W)

        ctk.CTkLabel(header_frame, text="Use preset templates or create your own custom yt-dlp commands.",
                 font=('Arial', 11), text_color='gray').grid(row=1, column=0, sticky=tk.W, pady=(0, 0))

        # Separator (using a frame as customtkinter doesn't have Separator)
        separator = ctk.CTkFrame(self.templates_tab, height=2, fg_color="gray")
        separator.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 3))

        # Main content area - two columns
        content_frame = ctk.CTkFrame(self.templates_tab)
        content_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))
        content_frame.columnconfigure(0, weight=3)  # Available Templates - 30%
        content_frame.columnconfigure(1, weight=7)  # Template Details - 70%
        content_frame.rowconfigure(0, weight=1)

        # LEFT COLUMN: Template list
        list_frame = ctk.CTkFrame(content_frame)
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 3))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)

        ctk.CTkLabel(list_frame, text="📋 Available Templates", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(5, 5), padx=5)

        # Listbox with scrollbars
        list_scroll_y = ctk.CTkScrollbar(list_frame, orientation="vertical")
        list_scroll_x = ctk.CTkScrollbar(list_frame, orientation="horizontal")
        self.template_listbox = tk.Listbox(list_frame,
                                          yscrollcommand=list_scroll_y.set,
                                          xscrollcommand=list_scroll_x.set,
                                          height=8, font=('Arial', 11), activestyle='dotbox')
        list_scroll_y.configure(command=self.template_listbox.yview)
        list_scroll_x.configure(command=self.template_listbox.xview)

        self.template_listbox.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0), pady=(0, 5))
        list_scroll_y.grid(row=1, column=1, sticky=(tk.N, tk.S), pady=(0, 5))
        list_scroll_x.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=(5, 0), pady=(0, 5))

        self.template_listbox.bind('<<ListboxSelect>>', self._on_template_select)

        # RIGHT COLUMN: Template details and actions
        right_column = ctk.CTkFrame(content_frame)
        right_column.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(3, 0))
        right_column.columnconfigure(0, weight=1)
        right_column.rowconfigure(0, weight=2)  # Details frame gets more space
        right_column.rowconfigure(1, weight=0)  # Action buttons - fixed height
        right_column.rowconfigure(2, weight=1)  # Add frame gets less space

        # Template details frame with scrollable content
        details_outer_frame = ctk.CTkFrame(right_column)
        details_outer_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 3))
        details_outer_frame.columnconfigure(0, weight=1)
        details_outer_frame.rowconfigure(0, weight=0)  # Label row - no expand
        details_outer_frame.rowconfigure(1, weight=1)  # Scrollable content - expand

        ctk.CTkLabel(details_outer_frame, text="📝 Template Details", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(5, 5), padx=5)

        # Use CTkScrollableFrame instead of raw tk.Canvas
        details_frame = ctk.CTkScrollableFrame(details_outer_frame)
        details_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=(0, 5))
        details_frame.columnconfigure(0, weight=1)

        # Name
        ctk.CTkLabel(details_frame, text="Name:", font=('Arial', 11, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 0))
        self.template_name_label = ctk.CTkLabel(details_frame, text="Select a template to view details",
                                            font=('Arial', 11), text_color='gray')
        self.template_name_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 2))

        # Description
        ctk.CTkLabel(details_frame, text="Description:", font=('Arial', 11, 'bold')).grid(
            row=2, column=0, sticky=tk.W, pady=(0, 0))
        self.template_desc_label = ctk.CTkLabel(details_frame, text="",
                                            font=('Arial', 11), wraplength=400, justify=tk.LEFT)
        self.template_desc_label.grid(row=3, column=0, sticky=tk.W, pady=(0, 2))

        # Command
        ctk.CTkLabel(details_frame, text="Command:", font=('Arial', 11, 'bold')).grid(
            row=4, column=0, sticky=tk.W, pady=(0, 0))

        cmd_frame = ctk.CTkFrame(details_frame)
        cmd_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 2))
        cmd_frame.columnconfigure(0, weight=1)

        self.template_cmd_text = tk.Text(cmd_frame, height=2, wrap=tk.WORD,
                                        font=('Consolas', 11), padx=4, pady=3,
                                        relief=tk.SOLID, borderwidth=1)
        self.template_cmd_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        # Add context menu (read-only mode)
        ContextMenu(self.template_cmd_text, read_only=True)

        # Action buttons (outside canvas, in right_column directly)
        btn_frame = ctk.CTkFrame(right_column)
        btn_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(3, 3))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self.template_use_btn = ctk.CTkButton(btn_frame, text="✓ Use Template",
                                          command=self._use_template, state='disabled')
        self.template_use_btn.grid(row=0, column=0, padx=(5, 3), pady=5, sticky=(tk.W, tk.E))

        self.template_delete_btn = ctk.CTkButton(btn_frame, text="🗑️ Delete",
                                             command=self._delete_template, state='disabled')
        self.template_delete_btn.grid(row=0, column=1, padx=(3, 5), pady=5, sticky=(tk.W, tk.E))

        # Add custom template section
        add_frame = ctk.CTkFrame(right_column)
        add_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N))
        add_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(add_frame, text="➕ Add Custom Template", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(5, 5), padx=5)

        # Name field
        ctk.CTkLabel(add_frame, text="Name:", font=('Arial', 11)).grid(
            row=1, column=0, sticky=tk.W, padx=(5, 8), pady=(0, 2))
        self.new_template_name = ctk.CTkEntry(add_frame, font=('Arial', 11))
        self.new_template_name.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 2), padx=(0, 5))
        # Add context menu
        ContextMenu(self.new_template_name)

        # Description field
        ctk.CTkLabel(add_frame, text="Description:", font=('Arial', 11)).grid(
            row=2, column=0, sticky=tk.W, padx=(5, 8), pady=(0, 2))
        self.new_template_desc = ctk.CTkEntry(add_frame, font=('Arial', 11))
        self.new_template_desc.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(0, 2), padx=(0, 5))
        # Add context menu
        ContextMenu(self.new_template_desc)

        # Command field
        ctk.CTkLabel(add_frame, text="Command:", font=('Arial', 11)).grid(
            row=3, column=0, sticky=(tk.W, tk.N), padx=(5, 8), pady=(0, 2))

        cmd_input_frame = ctk.CTkFrame(add_frame)
        cmd_input_frame.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=(0, 2), padx=(0, 5))
        cmd_input_frame.columnconfigure(0, weight=1)

        self.new_template_cmd = tk.Text(cmd_input_frame, height=2, wrap=tk.WORD,
                                       font=('Consolas', 11), padx=4, pady=3,
                                       relief=tk.SOLID, borderwidth=1)
        self.new_template_cmd.grid(row=0, column=0, sticky=(tk.W, tk.E))
        # Add context menu
        ContextMenu(self.new_template_cmd)

        # Add button
        add_btn_frame = ctk.CTkFrame(add_frame)
        add_btn_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 5))

        ctk.CTkButton(add_btn_frame, text="➕ Add Template", command=self._add_custom_template).pack(side=tk.RIGHT, padx=5)

        # Load templates
        self._refresh_template_list()
    
    def _create_ytdlp_section(self, parent):
        """Create yt-dlp executable path selection section"""
        ytdlp_label = ctk.CTkLabel(parent, text="yt-dlp Executable:", font=('Arial', 12, 'bold'))
        ytdlp_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 2))

        path_frame = ctk.CTkFrame(parent)
        path_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        path_frame.columnconfigure(0, weight=1)

        self.yt_dlp_entry = ctk.CTkEntry(path_frame, width=50)
        self.yt_dlp_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 3))
        # Add context menu
        ContextMenu(self.yt_dlp_entry)

        self.yt_dlp_browse_btn = ctk.CTkButton(path_frame, text="📁 Browse...", command=self.browse_yt_dlp)
        self.yt_dlp_browse_btn.grid(row=0, column=1, sticky=tk.W)

    def _create_url_section(self, parent):
        """Create video URL input section"""
        ctk.CTkLabel(parent, text="🔗 Video URL:", font=('Arial', 12, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 2))

        url_frame = ctk.CTkFrame(parent)
        url_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        url_frame.columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(url_frame, width=50, font=('Arial', 12))
        self.url_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 3))
        # Bind events for auto-fetch
        self.url_entry.bind('<KeyRelease>', self._on_url_changed)
        # Also bind Ctrl+V for paste events
        self.url_entry.bind('<Control-v>', self._on_url_changed)
        # Add context menu with paste callback for auto-fetch
        ContextMenu(self.url_entry, on_paste_callback=self._on_url_changed)

        paste_btn = ctk.CTkButton(url_frame, text="📋 Paste", command=self.paste_url)
        paste_btn.grid(row=0, column=1, padx=(0, 3))

        fetch_btn = ctk.CTkButton(url_frame, text="ℹ️ Fetch Info", command=self.fetch_video_info)
        fetch_btn.grid(row=0, column=2)

        # Store fetch button for later reference
        self.fetch_btn = fetch_btn

        # Auto-fetch timer
        self.auto_fetch_timer = None

        # Instruction label
        instruction_label = ctk.CTkLabel(
            parent,
            text="💡 Tip: Paste a video URL - it will auto-fetch info automatically. If auto-fetch doesn't work, click 'Fetch Info' to manually fetch available formats, resolutions, and framerates",
            font=('Arial', 10),
            text_color='gray',
            wraplength=400,
            justify=tk.LEFT
        )
        instruction_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 5))

    def _create_metadata_section(self, parent):
        """Create video metadata display section"""
        # Metadata frame (initially hidden)
        self.metadata_frame = ctk.CTkFrame(parent)
        self.metadata_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        self.metadata_frame.columnconfigure(1, weight=1)
        self.metadata_frame.rowconfigure(0, weight=0)

        # Add label for the frame
        ctk.CTkLabel(self.metadata_frame, text="Video Information", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(5, 5), padx=5)

        # Thumbnail (left side)
        self.thumbnail_label = ctk.CTkLabel(self.metadata_frame, text="")
        self.thumbnail_label.grid(row=1, column=0, rowspan=4, sticky=tk.NW, padx=(5, 5), pady=(0, 5))

        # Info container (right side)
        info_frame = ctk.CTkFrame(self.metadata_frame)
        info_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N), rowspan=4, pady=(0, 5), padx=(0, 5))
        info_frame.columnconfigure(0, weight=1)

        # Title
        title_frame = ctk.CTkFrame(info_frame)
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 1))
        title_frame.columnconfigure(1, weight=1)
        ctk.CTkLabel(title_frame, text="Title:", font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.metadata_title = ctk.CTkLabel(title_frame, text="", wraplength=400, font=('Arial', 11))
        self.metadata_title.grid(row=0, column=1, sticky=tk.W, padx=(3, 0))

        # Duration
        duration_frame = ctk.CTkFrame(info_frame)
        duration_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 1))
        duration_frame.columnconfigure(1, weight=1)
        ctk.CTkLabel(duration_frame, text="Duration:", font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.metadata_duration = ctk.CTkLabel(duration_frame, text="", font=('Arial', 11))
        self.metadata_duration.grid(row=0, column=1, sticky=tk.W, padx=(3, 0))

        # Uploader
        uploader_frame = ctk.CTkFrame(info_frame)
        uploader_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 1))
        uploader_frame.columnconfigure(1, weight=1)
        ctk.CTkLabel(uploader_frame, text="Uploader:", font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.metadata_uploader = ctk.CTkLabel(uploader_frame, text="", font=('Arial', 11))
        self.metadata_uploader.grid(row=0, column=1, sticky=tk.W, padx=(3, 0))

        # Views
        views_frame = ctk.CTkFrame(info_frame)
        views_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))
        views_frame.columnconfigure(1, weight=1)
        ctk.CTkLabel(views_frame, text="Views:", font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.metadata_views = ctk.CTkLabel(views_frame, text="", font=('Arial', 11))
        self.metadata_views.grid(row=0, column=1, sticky=tk.W, padx=(3, 0))

        # Hide metadata frame initially
        self.metadata_frame.grid_remove()

    def _create_trim_section(self, parent):
        """Create trim/cut controls section"""
        # Trim frame (initially hidden) - fixed size, don't expand
        self.trim_frame = ctk.CTkFrame(parent)
        self.trim_frame.grid(row=3, column=0, sticky=tk.W, pady=(0, 5))

        ctk.CTkLabel(self.trim_frame, text="✂️ Trim Video", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(5, 5), padx=5)

        # Enable trim checkbox
        self.trim_enabled = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.trim_frame, text="Enable trimming",
                       variable=self.trim_enabled,
                       command=self._toggle_trim_controls).grid(
            row=1, column=0, sticky=tk.W, pady=(0, 5), padx=5)

        # Time inputs frame (Start and End on same line) - fixed size
        time_frame = ctk.CTkFrame(self.trim_frame)
        time_frame.grid(row=2, column=0, sticky=tk.W, padx=5, pady=(0, 5))

        # Start time
        ctk.CTkLabel(time_frame, text="Start:", font=('Arial', 11)).grid(
            row=0, column=0, sticky=tk.W, padx=(5, 3), pady=5)
        self.trim_start_entry = TimeEntry(time_frame, width=120, state='disabled')
        self.trim_start_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 10), pady=5)

        # End time
        ctk.CTkLabel(time_frame, text="End:", font=('Arial', 11)).grid(
            row=0, column=2, sticky=tk.W, padx=(5, 3), pady=5)
        self.trim_end_entry = TimeEntry(time_frame, width=120, state='disabled')
        self.trim_end_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 5), pady=5)

        # Help text
        help_text = ctk.CTkLabel(self.trim_frame,
                             text="Format: HH:MM:SS  |  ↑↓ to adjust  |  Del/Backspace resets digit to 0",
                             font=('Arial', 10), text_color='gray')
        help_text.grid(row=3, column=0, sticky=tk.W, pady=(2, 5), padx=5)

        # Hide trim frame initially
        self.trim_frame.grid_remove()

    def _create_convert_section(self, parent):
        """Create convert to format section"""
        # Convert frame (initially hidden)
        self.convert_frame = ctk.CTkFrame(parent)
        self.convert_frame.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        self.convert_frame.columnconfigure(0, weight=0)

        ctk.CTkLabel(self.convert_frame, text="🔄 Remux", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(5, 5), padx=5)

        # Enable convert checkbox
        self.convert_enabled = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.convert_frame, text="Enable remuxing",
                       variable=self.convert_enabled,
                       command=self._toggle_convert_controls).grid(
            row=1, column=0, sticky=tk.W, pady=(0, 5), padx=5)

        # Format buttons frame
        self.convert_format_frame = ctk.CTkFrame(self.convert_frame)
        self.convert_format_frame.grid(row=2, column=0, sticky=tk.W, padx=5, pady=(0, 5))

        # Convert format variable
        self.convert_format_var = tk.StringVar(value="mp4")

        # Video formats
        self.video_convert_formats = ['mp4', 'mkv', 'avi', 'mov', 'webm', 'flv']
        # Audio formats
        self.audio_convert_formats = ['mp3', 'wav', 'aac', 'm4a', 'opus', 'vorbis', 'flac', 'ogg']

        # Create format radio buttons (will be updated based on mode)
        self._update_convert_format_options()

        # Help text
        help_text = ctk.CTkLabel(self.convert_frame,
                             text="Convert downloaded file to selected format using ffmpeg",
                             font=('Arial', 10), text_color='gray')
        help_text.grid(row=3, column=0, sticky=tk.W, pady=(2, 0), padx=5)

        # Hide convert frame initially
        self.convert_frame.grid_remove()

    def _toggle_convert_controls(self):
        """Toggle convert control states"""
        if self.convert_enabled.get():
            for child in self.convert_format_frame.winfo_children():
                child.configure(state='normal')
        else:
            for child in self.convert_format_frame.winfo_children():
                child.configure(state='disabled')

    def _update_convert_format_options(self):
        """Update convert format options based on current mode"""
        # Clear existing buttons safely (may fail during rapid resize)
        for child in self.convert_format_frame.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

        mode = self.mode_var.get() if hasattr(self, 'mode_var') else 'auto'

        # Choose formats based on mode
        if mode == 'audio':
            formats = self.audio_convert_formats
        else:
            formats = self.video_convert_formats

        # Create radio buttons
        for idx, fmt in enumerate(formats):
            state = 'normal' if self.convert_enabled.get() else 'disabled'
            radio = ctk.CTkRadioButton(
                self.convert_format_frame,
                text=fmt.upper(),
                value=fmt,
                variable=self.convert_format_var,
                state=state
            )
            radio.grid(row=0, column=idx, padx=(0, 5))

        # Set default value
        if formats:
            self.convert_format_var.set(formats[0])

    def _create_output_section(self, parent):
        """Create output directory selection section"""
        ctk.CTkLabel(parent, text="📂 Output Directory:", font=('Arial', 12, 'bold')).grid(
            row=4, column=0, sticky=tk.W, pady=(0, 2))

        output_frame = ctk.CTkFrame(parent)
        output_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        output_frame.columnconfigure(0, weight=1)

        self.output_entry = ctk.CTkEntry(output_frame, width=50, font=('Arial', 12))
        self.output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 3))
        self.output_entry.insert(0, str(Path.home() / "Downloads"))
        # Add context menu
        ContextMenu(self.output_entry)

        browse_btn = ctk.CTkButton(output_frame, text="📁 Browse...", command=self.browse_output)
        browse_btn.grid(row=0, column=1)

    def _create_format_section(self, parent):
        """Create format selection section"""
        # Label frame for format and mode selection
        self.format_label_frame = ctk.CTkFrame(parent)
        self.format_label_frame.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        self.format_label_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(self.format_label_frame, text="🎬 Download Options", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(5, 5), padx=5)

        # Mode selection (Video Only, Audio Only, Auto)
        mode_frame = ctk.CTkFrame(self.format_label_frame)
        mode_frame.grid(row=1, column=0, sticky=tk.W, pady=(0, 5), padx=5)

        ctk.CTkLabel(mode_frame, text="Mode:", font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=(0, 8))

        self.mode_var = tk.StringVar(value="auto")
        ctk.CTkRadioButton(mode_frame, text="🎥 Video", variable=self.mode_var,
                       value="video", command=self._on_mode_changed).pack(side=tk.LEFT, padx=(0, 10))
        ctk.CTkRadioButton(mode_frame, text="🎵 Audio Only", variable=self.mode_var,
                       value="audio", command=self._on_mode_changed).pack(side=tk.LEFT, padx=(0, 10))
        ctk.CTkRadioButton(mode_frame, text="⚙️ Auto", variable=self.mode_var,
                       value="auto", command=self._on_mode_changed).pack(side=tk.LEFT)

        # Format selection
        format_frame = ctk.CTkFrame(self.format_label_frame)
        format_frame.grid(row=2, column=0, sticky=tk.W, pady=(0, 5), padx=5)

        ctk.CTkLabel(format_frame, text="Format:", font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=(0, 8))

        self.format_var = tk.StringVar(value="mp4")
        self.format_radios = []
        self.format_radio_frame = ctk.CTkFrame(format_frame)
        self.format_radio_frame.pack(side=tk.LEFT)
        self._update_format_options(['MP4', 'MP3'])

        # Hide initially
        self.format_label_frame.grid_remove()

    def _create_quality_section(self, parent):
        """Create quality selection section"""
        self.quality_label_frame = ctk.CTkFrame(parent)
        self.quality_label_frame.grid(row=8, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        self.quality_label_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(self.quality_label_frame, text="⭐ Quality & Resolution", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(5, 5), padx=5)

        self.quality_var = tk.StringVar(value="best")

        # Quality combobox
        ctk.CTkLabel(self.quality_label_frame, text="Resolution:", font=('Arial', 11, 'bold')).grid(
            row=1, column=0, sticky=tk.W, pady=(0, 3), padx=5)

        self.quality_combo = ctk.CTkComboBox(self.quality_label_frame, variable=self.quality_var, width=30)
        self.quality_combo.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 5), padx=5)

        # Audio bitrate selection (in a separate frame so it can be hidden independently)
        self.audio_bitrate_frame = ctk.CTkFrame(self.quality_label_frame)
        self.audio_bitrate_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), padx=5)
        self.audio_bitrate_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(self.audio_bitrate_frame, text="Audio Bitrate:", font=('Arial', 11, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 3))

        self.audio_bitrate_var = tk.StringVar(value="best")
        self.audio_bitrate_combo = ctk.CTkComboBox(self.audio_bitrate_frame, variable=self.audio_bitrate_var, width=30)
        self.audio_bitrate_combo.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # Store mapping of display names to values
        self.quality_mapping = {}
        self.audio_bitrate_mapping = {}

        # Set default options
        self._update_quality_options(['Best Quality', '1080p', '720p', '480p', '360p', 'Worst (smallest)'],
                                     ['best', '1080', '720', '480', '360', 'worst'])
        self._update_audio_bitrate_options(['Best', '320k', '256k', '192k', '128k'],
                                          ['best', '320', '256', '192', '128'])

        # Hide initially
        self.quality_label_frame.grid_remove()

    def _create_download_button(self, parent):
        """Create download button and progress bar"""
        # Button frame for Download and Cancel buttons
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.grid(row=9, column=0, pady=(0, 5), sticky=(tk.W, tk.E))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=0)

        # Download button (disabled until metadata is fetched)
        self.download_btn = ctk.CTkButton(button_frame, text="📥 Download",
                                       command=self.start_download,
                                       state='disabled')
        self.download_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))

        # Cancel button (hidden initially)
        self.cancel_btn = ctk.CTkButton(button_frame, text="⏹️ Cancel",
                                     command=self.cancel_download, state='disabled')
        self.cancel_btn.grid(row=0, column=1, sticky=tk.E)

        # Progress bar frame (below buttons, hidden initially)
        self.download_progress_frame = ctk.CTkFrame(parent)
        self.download_progress_frame.grid(row=10, column=0, sticky=(tk.W, tk.E), pady=(5, 8))
        self.download_progress_frame.columnconfigure(0, weight=1)

        self.download_progress_label = ctk.CTkLabel(self.download_progress_frame, text="",
                                                 font=('Arial', 12))
        self.download_progress_label.grid(row=0, column=0, sticky=tk.W, pady=(5, 5), padx=5)

        self.download_progress_bar = ctk.CTkProgressBar(self.download_progress_frame,
                                                     mode='determinate')
        self.download_progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=(0, 5))
        self.download_progress_bar.set(0)

        # Initially hide progress
        self.download_progress_frame.grid_remove()

    def _create_output_log(self, parent):
        """Create output log section"""
        self.output_text = ctk.CTkTextbox(parent, wrap="word")
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        self.output_text.configure(state="disabled")
        # Add context menu (read-only mode)
        ContextMenu(self.output_text, read_only=True)

    def _create_status_bar(self, parent):
        """Create status bar"""
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ctk.CTkLabel(parent, textvariable=self.status_var, anchor=tk.W)
        status_bar.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(5, 0), padx=5)
    
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
        mode = self.mode_var.get() if hasattr(self, 'mode_var') else 'auto'

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

        # Create radio buttons for each format
        for fmt in filtered_formats:
            fmt_lower = fmt.lower()
            is_video = fmt_lower in video_formats
            radio = ctk.CTkRadioButton(
                self.format_radio_frame,
                text=f"🎥 {fmt.upper()}" if is_video else f"🎵 {fmt.upper()}",
                variable=self.format_var,
                value=fmt_lower
            )
            radio.pack(side=tk.LEFT, padx=(0, 10))
            self.format_radios.append(radio)

        # Set default value based on mode
        if mode == 'audio':
            # Prefer m4a for audio
            if 'm4a' in [f.lower() for f in filtered_formats]:
                self.format_var.set('m4a')
            else:
                self.format_var.set(filtered_formats[0].lower())
        else:
            # Prefer mp4 for video/auto
            if 'mp4' in [f.lower() for f in filtered_formats]:
                self.format_var.set('mp4')
            else:
                self.format_var.set(filtered_formats[0].lower())

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

    def _on_url_changed(self, event=None):
        """Handle URL entry changes for auto-fetch"""
        url = self.url_entry.get().strip()

        # Cancel previous timer if exists
        if self.auto_fetch_timer:
            self.root.after_cancel(self.auto_fetch_timer)

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
                convert_format=convert_format
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
            convert_format=convert_format
        )

    def _start_playlist_download(self, yt_dlp_path, selected_videos, output_dir, format_type, quality, trim_start, trim_end, mode, convert_enabled=False, convert_format=""):
        """Start downloading multiple videos from a playlist"""
        import threading

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
                    convert_format=convert_format
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
                # Clear template after use
                self.current_template_command = None

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

    # yt-dlp Download Tab Methods

    def _browse_ytdlp_save_location(self):
        """Browse for yt-dlp save location"""
        filename = filedialog.asksaveasfilename(
            title="Save yt-dlp executable as",
            defaultextension=".exe",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")],
            initialfile="yt-dlp.exe"
        )
        if filename:
            self.ytdlp_save_entry.delete(0, tk.END)
            self.ytdlp_save_entry.insert(0, filename)

    def _download_ytdlp(self):
        """Download yt-dlp executable"""
        version_type = self.ytdlp_version_var.get()
        save_path = self.ytdlp_save_entry.get().strip()

        if not save_path:
            messagebox.showerror("Error", "Please specify a save location")
            return

        # Disable button during download
        self.ytdlp_download_btn.configure(state='disabled')
        self.ytdlp_progress_frame.grid()
        self.ytdlp_progress_bar.set(0)
        self.ytdlp_progress_label.configure(text=f"Preparing to download {version_type} version...")

        # Switch to log tab
        self.tabview.set("📄 Output Log")

        # Clear log
        self.output_text.configure(state='normal')
        self.output_text.delete(1.0, tk.END)
        self.output_text.configure(state='disabled')

        def on_progress(progress_info):
            downloaded = progress_info.get('downloaded', 0)
            total = progress_info.get('total', 0)
            speed = progress_info.get('speed', 0)
            eta_seconds = progress_info.get('eta_seconds', 0)

            if total > 0:
                percent = (downloaded / total) * 100
                self.ytdlp_progress_bar.set(percent / 100.0)

                # Format speed and ETA
                speed_str = self._format_speed(speed)
                eta_str = self._format_time(eta_seconds)

                # Format sizes
                downloaded_mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)

                self.ytdlp_progress_label.configure(
                    text=f"Downloading: {downloaded_mb:.2f}MiB / {total_mb:.2f}MiB ({percent:.1f}%) | {speed_str} | ETA {eta_str}"
                )

        def on_complete(file_path):
            self.ytdlp_download_btn.configure(state='normal')
            self.ytdlp_progress_bar.set(1.0)
            self.ytdlp_progress_label.configure(text="✓ Download completed!")
            self.status_var.set("yt-dlp downloaded successfully")

            # Set the path in the main yt-dlp entry
            self.yt_dlp_entry.delete(0, tk.END)
            self.yt_dlp_entry.insert(0, file_path)
            self.config.set('yt_dlp_path', file_path)

            # Hide progress bar after 2 seconds
            self.root.after(2000, self.ytdlp_progress_frame.grid_remove)

            messagebox.showinfo("Success", f"yt-dlp downloaded successfully!\n\nSaved to:\n{file_path}")

        def on_error(error_msg):
            self.ytdlp_download_btn.configure(state='normal')
            self.ytdlp_progress_frame.grid_remove()
            self.status_var.set("yt-dlp download failed")
            messagebox.showerror("Download Error", f"Failed to download yt-dlp:\n{error_msg}")

        # Start download
        self.ytdlp_downloader.download(
            version_type=version_type,
            output_path=save_path,
            on_progress=on_progress,
            on_log=self.log_message,
            on_complete=on_complete,
            on_error=on_error
        )

    # FFmpeg Download Tab Methods

    def _browse_ffmpeg_save_location(self):
        """Browse for FFmpeg save location"""
        filename = filedialog.asksaveasfilename(
            title="Save FFmpeg executable as",
            defaultextension=".exe",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")],
            initialfile="ffmpeg.exe"
        )
        if filename:
            self.ffmpeg_save_entry.delete(0, tk.END)
            self.ffmpeg_save_entry.insert(0, filename)

    def _download_ffmpeg(self):
        """Download FFmpeg executable"""
        save_path = self.ffmpeg_save_entry.get().strip()

        if not save_path:
            messagebox.showerror("Error", "Please specify a save location")
            return

        # Disable button during download
        self.ffmpeg_download_btn.configure(state='disabled')
        self.ffmpeg_progress_frame.grid()
        self.ffmpeg_progress_bar.set(0)
        self.ffmpeg_progress_label.configure(text="Preparing to download FFmpeg...")

        # Switch to log tab
        self.tabview.set("📄 Output Log")

        # Clear log
        self.output_text.configure(state='normal')
        self.output_text.delete(1.0, tk.END)
        self.output_text.configure(state='disabled')

        def on_progress(progress_info):
            downloaded = progress_info.get('downloaded', 0)
            total = progress_info.get('total', 0)
            speed = progress_info.get('speed', 0)
            eta_seconds = progress_info.get('eta_seconds', 0)

            if total > 0:
                percent = (downloaded / total) * 100
                self.ffmpeg_progress_bar.set(percent / 100.0)

                # Format speed and ETA
                speed_str = self._format_speed(speed)
                eta_str = self._format_time(eta_seconds)

                # Format sizes
                downloaded_mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)

                self.ffmpeg_progress_label.configure(
                    text=f"Downloading: {downloaded_mb:.2f}MiB / {total_mb:.2f}MiB ({percent:.1f}%) | {speed_str} | ETA {eta_str}"
                )

        def on_complete(file_path):
            self.ffmpeg_download_btn.configure(state='normal')
            self.ffmpeg_progress_bar.set(1.0)
            self.ffmpeg_progress_label.configure(text="✓ Download completed!")
            self.status_var.set("FFmpeg downloaded successfully")

            # Hide progress bar after 2 seconds
            self.root.after(2000, self.ffmpeg_progress_frame.grid_remove)

            messagebox.showinfo("Success", f"FFmpeg downloaded successfully!\n\nSaved to:\n{file_path}")

        def on_error(error_msg):
            self.ffmpeg_download_btn.configure(state='normal')
            self.ffmpeg_progress_frame.grid_remove()
            self.status_var.set("FFmpeg download failed")
            messagebox.showerror("Download Error", f"Failed to download FFmpeg:\n{error_msg}")

        # Start download
        self.ffmpeg_downloader.download(
            output_path=save_path,
            on_progress=on_progress,
            on_log=self.log_message,
            on_complete=on_complete,
            on_error=on_error
        )

    # Template Tab Methods

    def _refresh_template_list(self):
        """Refresh the template listbox"""
        self.template_listbox.delete(0, tk.END)

        templates = self.template_manager.get_all_templates()
        for template in templates:
            prefix = "[Preset] " if template.get('is_preset', False) else "[Custom] "
            self.template_listbox.insert(tk.END, prefix + template['name'])

    def _on_template_select(self, event):
        """Handle template selection"""
        selection = self.template_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        templates = self.template_manager.get_all_templates()

        if index < len(templates):
            template = templates[index]

            # Update details
            self.template_name_label.configure(text=template['name'])
            self.template_desc_label.configure(text=template['description'])

            self.template_cmd_text.delete('1.0', tk.END)
            self.template_cmd_text.insert('1.0', template['command'])

            # Enable buttons
            self.template_use_btn.configure(state='normal')

            # Only enable delete for custom templates
            if not template.get('is_preset', False):
                self.template_delete_btn.configure(state='normal')
            else:
                self.template_delete_btn.configure(state='disabled')

    def _use_template(self):
        """Use the selected template for download"""
        selection = self.template_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        templates = self.template_manager.get_all_templates()

        if index < len(templates):
            template = templates[index]

            # Show confirmation dialog
            result = messagebox.askyesno(
                "Use Template",
                f"Use template '{template['name']}'?\n\n"
                f"This will execute the following command:\n\n"
                f"{template['command']}\n\n"
                f"Make sure you have entered a URL and output directory in the Download tab."
            )

            if result:
                # Switch to download tab
                self.tabview.set("📥 Download")

                # Store the template command for use
                self.current_template_command = template['command']

                messagebox.showinfo(
                    "Template Ready",
                    f"Template '{template['name']}' is ready.\n\n"
                    f"Note: The template will override the standard format/quality settings.\n"
                    f"Click Download to execute with this template."
                )

    def _add_custom_template(self):
        """Add a new custom template"""
        name = self.new_template_name.get().strip()
        description = self.new_template_desc.get().strip()
        command = self.new_template_cmd.get('1.0', tk.END).strip()

        if not name or not description or not command:
            messagebox.showerror("Error", "Please fill in all fields")
            return

        if self.template_manager.add_template(name, description, command):
            messagebox.showinfo("Success", f"Template '{name}' added successfully!")

            # Clear fields
            self.new_template_name.delete(0, tk.END)
            self.new_template_desc.delete(0, tk.END)
            self.new_template_cmd.delete('1.0', tk.END)

            # Refresh list
            self._refresh_template_list()
        else:
            messagebox.showerror("Error", f"Template '{name}' already exists")

    def _delete_template(self):
        """Delete the selected custom template"""
        selection = self.template_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        templates = self.template_manager.get_all_templates()

        if index < len(templates):
            template = templates[index]

            if template.get('is_preset', False):
                messagebox.showerror("Error", "Cannot delete preset templates")
                return

            result = messagebox.askyesno(
                "Delete Template",
                f"Are you sure you want to delete template '{template['name']}'?"
            )

            if result:
                if self.template_manager.delete_template(template['name']):
                    messagebox.showinfo("Success", "Template deleted successfully")
                    self._refresh_template_list()

                    # Clear details
                    self.template_name_label.configure(text="")
                    self.template_desc_label.configure(text="")
                    self.template_cmd_text.delete('1.0', tk.END)
                    self.template_use_btn.configure(state='disabled')
                    self.template_delete_btn.configure(state='disabled')
                else:
                    messagebox.showerror("Error", "Failed to delete template")

