"""Main application window"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
from pathlib import Path
from io import BytesIO
import urllib.request

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from ..config import ConfigManager
from ..downloader import Downloader
from ..metadata import MetadataFetcher
from ..ytdlp_manager import YtdlpDownloader
from ..templates import TemplateManager


class ToolTip:
    """Create a tooltip for a given widget"""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        """Display the tooltip"""
        if self.tooltip_window or not self.text:
            return

        x, y, _, _ = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                        background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                        font=("Arial", 8, "normal"), padx=5, pady=3)
        label.pack()

    def hide_tooltip(self, event=None):
        """Hide the tooltip"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


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

        # Initialize template manager
        self.template_manager = TemplateManager()

        # Store current video metadata
        self.current_metadata = None

        # Store current template command (if using template)
        self.current_template_command = None

        # Create UI
        self.create_widgets()
        
        # Load saved yt-dlp path
        saved_path = self.config.get('yt_dlp_path', '')
        if saved_path:
            self.yt_dlp_entry.insert(0, saved_path)

    def _configure_styles(self):
        """Configure custom styles for the application"""
        style = ttk.Style()

        # Configure colors
        self.colors = {
            'primary': '#2196F3',      # Blue
            'success': '#4CAF50',      # Green
            'warning': '#FF9800',      # Orange
            'error': '#F44336',        # Red
            'bg_light': '#F5F5F5',     # Light gray
            'text_dark': '#212121',    # Dark gray
            'text_light': '#757575'    # Medium gray
        }

        # Try to configure accent button style
        try:
            style.configure('Accent.TButton',
                          font=('Arial', 10, 'bold'),
                          padding=8)
        except:
            pass

        # Configure label frames
        try:
            style.configure('TLabelframe.Label',
                          font=('Arial', 9, 'bold'),
                          foreground=self.colors['primary'])
        except:
            pass

    def create_widgets(self):
        """Create and layout all GUI widgets"""
        # Main container with minimal padding
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights for responsiveness
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        # yt-dlp Path Section (always visible at top)
        self._create_ytdlp_section(main_frame)

        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))

        # Create tabs with canvas for scrolling
        # Download tab with scrollbar
        self.download_canvas_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.download_canvas_frame, text="📥 Download")

        self.download_canvas = tk.Canvas(self.download_canvas_frame, highlightthickness=0)
        self.download_scrollbar = ttk.Scrollbar(self.download_canvas_frame, orient="vertical", command=self.download_canvas.yview)
        self.download_tab = ttk.Frame(self.download_canvas, padding=(8, 8, 8, 8))

        self.download_canvas.configure(yscrollcommand=self.download_scrollbar.set)
        # Don't pack scrollbar yet - will show it when needed
        self.download_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure canvas to anchor content at top
        self.download_canvas_frame.grid_rowconfigure(0, weight=1)
        self.download_canvas_frame.grid_columnconfigure(0, weight=1)

        self.canvas_window = self.download_canvas.create_window((0, 0), window=self.download_tab, anchor=tk.NW)

        # Update scroll region when content changes
        def configure_scroll_region(event):
            self.download_canvas.configure(scrollregion=self.download_canvas.bbox("all"))
            self._check_scrollbar_needed()
        self.download_tab.bind("<Configure>", configure_scroll_region)

        # Bind mousewheel to canvas - only scroll if scrollbar is visible
        def on_mousewheel(event):
            if self.scrollbar_visible:
                self.download_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.download_canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Make canvas window expand with canvas
        def configure_canvas_width(event):
            self.download_canvas.itemconfig(self.canvas_window, width=event.width)
        self.download_canvas.bind("<Configure>", configure_canvas_width)

        # Get yt-dlp tab
        self.ytdlp_tab = ttk.Frame(self.notebook, padding="8")
        self.notebook.add(self.ytdlp_tab, text="⚙️ Get yt-dlp")

        # Templates tab
        self.templates_tab = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(self.templates_tab, text="📋 Templates")

        # Log tab
        self.log_tab = ttk.Frame(self.notebook, padding="8")
        self.notebook.add(self.log_tab, text="📄 Output Log")

        # Configure tab weights
        self.download_tab.columnconfigure(0, weight=1)
        self.ytdlp_tab.columnconfigure(0, weight=1)
        self.templates_tab.columnconfigure(0, weight=1)
        self.log_tab.columnconfigure(0, weight=1)
        self.log_tab.rowconfigure(0, weight=1)

        # Track if scrollbar is shown
        self.scrollbar_visible = False

        # Populate Download Tab
        self._create_download_tab_content()

        # Populate Get yt-dlp Tab
        self._create_ytdlp_tab_content()

        # Populate Templates Tab
        self._create_templates_tab_content()

        # Populate Log Tab
        self._create_log_tab_content()

        # Status Bar (always visible at bottom)
        self._create_status_bar(main_frame)

    def _create_download_tab_content(self):
        """Create content for download tab"""
        # Video URL Section
        self._create_url_section(self.download_tab)

        # Video Metadata Section
        self._create_metadata_section(self.download_tab)

        # Trim/Cut Section
        self._create_trim_section(self.download_tab)

        # Output Directory Section
        self._create_output_section(self.download_tab)

        # Format Selection Section
        self._create_format_section(self.download_tab)

        # Quality Selection Section
        self._create_quality_section(self.download_tab)

        # Download Button
        self._create_download_button(self.download_tab)

    def _create_log_tab_content(self):
        """Create content for log tab"""
        # Output log
        self._create_output_log(self.log_tab)

    def _create_ytdlp_tab_content(self):
        """Create content for Get yt-dlp tab"""
        # Title
        ttk.Label(self.ytdlp_tab, text="Download yt-dlp Executable",
                 font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Description
        desc_text = "Download the latest yt-dlp executable directly from GitHub.\nChoose between Stable, Nightly, or Master builds."
        ttk.Label(self.ytdlp_tab, text=desc_text, font=('Arial', 9)).grid(
            row=1, column=0, sticky=tk.W, pady=(0, 15))

        # Version selection
        version_frame = ttk.LabelFrame(self.ytdlp_tab, text="Select Version", padding="10")
        version_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        version_frame.columnconfigure(0, weight=1)

        self.ytdlp_version_var = tk.StringVar(value="stable")

        ttk.Radiobutton(version_frame, text="Stable - Recommended for most users",
                       variable=self.ytdlp_version_var, value="stable").grid(
            row=0, column=0, sticky=tk.W, pady=2)

        ttk.Radiobutton(version_frame, text="Nightly - Latest features and fixes",
                       variable=self.ytdlp_version_var, value="nightly").grid(
            row=1, column=0, sticky=tk.W, pady=2)

        ttk.Radiobutton(version_frame, text="Master - Bleeding edge (may be unstable)",
                       variable=self.ytdlp_version_var, value="master").grid(
            row=2, column=0, sticky=tk.W, pady=2)

        # Output location
        location_frame = ttk.LabelFrame(self.ytdlp_tab, text="Save Location", padding="10")
        location_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        location_frame.columnconfigure(0, weight=1)

        self.ytdlp_save_entry = ttk.Entry(location_frame, width=50)
        self.ytdlp_save_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        default_path = str(Path.home() / "Downloads" / "yt-dlp.exe")
        self.ytdlp_save_entry.insert(0, default_path)

        ttk.Button(location_frame, text="📁 Browse...",
                  command=self._browse_ytdlp_save_location).grid(row=0, column=1)

        # Progress bar
        self.ytdlp_progress_frame = ttk.Frame(self.ytdlp_tab)
        self.ytdlp_progress_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        self.ytdlp_progress_frame.columnconfigure(0, weight=1)

        self.ytdlp_progress_label = ttk.Label(self.ytdlp_progress_frame, text="",
                                             font=('Arial', 9))
        self.ytdlp_progress_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        self.ytdlp_progress_bar = ttk.Progressbar(self.ytdlp_progress_frame,
                                                  mode='determinate', length=400)
        self.ytdlp_progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # Initially hide progress
        self.ytdlp_progress_frame.grid_remove()

        # Download button
        self.ytdlp_download_btn = ttk.Button(self.ytdlp_tab, text="⬇️ Download yt-dlp",
                                            command=self._download_ytdlp,
                                            style='Accent.TButton')
        self.ytdlp_download_btn.grid(row=5, column=0, pady=(0, 10), sticky=(tk.W, tk.E))

        # Info text
        info_text = ("After downloading, the path will be automatically set in the main tab.\n"
                    "You can also manually browse for an existing yt-dlp.exe file.")
        ttk.Label(self.ytdlp_tab, text=info_text, font=('Arial', 8),
                 foreground='gray').grid(row=6, column=0, sticky=tk.W)

    def _create_templates_tab_content(self):
        """Create content for Templates tab"""
        # Configure templates tab grid weights
        self.templates_tab.rowconfigure(2, weight=1)  # Make content frame expand

        # Title and description
        header_frame = ttk.Frame(self.templates_tab)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 1))
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(header_frame, text="Custom yt-dlp Command Templates",
                 font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky=tk.W)

        ttk.Label(header_frame, text="Use preset templates or create your own custom yt-dlp commands.",
                 font=('Arial', 8), foreground='gray').grid(row=1, column=0, sticky=tk.W, pady=(0, 0))

        # Separator
        ttk.Separator(self.templates_tab, orient='horizontal').grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 3))

        # Main content area - two columns
        content_frame = ttk.Frame(self.templates_tab)
        content_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))
        content_frame.columnconfigure(0, weight=3)  # Available Templates - 30%
        content_frame.columnconfigure(1, weight=7)  # Template Details - 70%
        content_frame.rowconfigure(0, weight=1)

        # LEFT COLUMN: Template list
        list_frame = ttk.LabelFrame(content_frame, text="📋 Available Templates", padding="3")
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 3))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Listbox with scrollbars
        list_scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        list_scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL)
        self.template_listbox = tk.Listbox(list_frame,
                                          yscrollcommand=list_scroll_y.set,
                                          xscrollcommand=list_scroll_x.set,
                                          height=8, font=('Arial', 8), activestyle='dotbox')
        list_scroll_y.config(command=self.template_listbox.yview)
        list_scroll_x.config(command=self.template_listbox.xview)

        self.template_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_scroll_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        list_scroll_x.grid(row=1, column=0, sticky=(tk.W, tk.E))

        self.template_listbox.bind('<<ListboxSelect>>', self._on_template_select)

        # RIGHT COLUMN: Template details and actions
        right_column = ttk.Frame(content_frame)
        right_column.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(3, 0))
        right_column.columnconfigure(0, weight=1)
        right_column.rowconfigure(0, weight=2)  # Details frame gets more space
        right_column.rowconfigure(1, weight=1)  # Add frame gets less space

        # Template details frame with canvas for scrolling
        details_outer_frame = ttk.LabelFrame(right_column, text="📝 Template Details", padding="3")
        details_outer_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 3))
        details_outer_frame.columnconfigure(0, weight=1)
        details_outer_frame.rowconfigure(0, weight=1)

        # Create canvas and scrollbar for details
        details_canvas = tk.Canvas(details_outer_frame, highlightthickness=0)
        details_scrollbar = ttk.Scrollbar(details_outer_frame, orient="vertical", command=details_canvas.yview)
        details_frame = ttk.Frame(details_canvas)

        details_canvas.configure(yscrollcommand=details_scrollbar.set)

        details_canvas_window = details_canvas.create_window((0, 0), window=details_frame, anchor=tk.NW)

        # Update scroll region and scrollbar visibility
        def update_scrollbar_visibility():
            details_canvas.configure(scrollregion=details_canvas.bbox("all"))
            # Show scrollbar only if needed
            canvas_height = details_canvas.winfo_height()
            content_height = details_frame.winfo_reqheight()
            if content_height > canvas_height and canvas_height > 1:
                details_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
            else:
                details_scrollbar.grid_remove()

        def configure_details_scroll(event):
            update_scrollbar_visibility()

        details_frame.bind("<Configure>", configure_details_scroll)

        # Make canvas window expand with canvas and update scrollbar
        def configure_details_canvas_width(event):
            details_canvas.itemconfig(details_canvas_window, width=event.width)
            update_scrollbar_visibility()

        details_canvas.bind("<Configure>", configure_details_canvas_width)

        details_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        details_frame.columnconfigure(0, weight=1)

        # Name
        ttk.Label(details_frame, text="Name:", font=('Arial', 8, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 0))
        self.template_name_label = ttk.Label(details_frame, text="Select a template to view details",
                                            font=('Arial', 8), foreground='gray')
        self.template_name_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 2))

        # Description
        ttk.Label(details_frame, text="Description:", font=('Arial', 8, 'bold')).grid(
            row=2, column=0, sticky=tk.W, pady=(0, 0))
        self.template_desc_label = ttk.Label(details_frame, text="",
                                            font=('Arial', 8), wraplength=400, justify=tk.LEFT)
        self.template_desc_label.grid(row=3, column=0, sticky=tk.W, pady=(0, 2))

        # Command
        ttk.Label(details_frame, text="Command:", font=('Arial', 8, 'bold')).grid(
            row=4, column=0, sticky=tk.W, pady=(0, 0))

        cmd_frame = ttk.Frame(details_frame)
        cmd_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 2))
        cmd_frame.columnconfigure(0, weight=1)

        self.template_cmd_text = tk.Text(cmd_frame, height=2, wrap=tk.WORD,
                                        font=('Consolas', 8), padx=4, pady=3,
                                        relief=tk.SOLID, borderwidth=1)
        self.template_cmd_text.grid(row=0, column=0, sticky=(tk.W, tk.E))

        # Action buttons
        btn_frame = ttk.Frame(details_frame)
        btn_frame.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=(2, 0))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self.template_use_btn = ttk.Button(btn_frame, text="✓ Use Template",
                                          command=self._use_template, state='disabled',
                                          style='Accent.TButton')
        self.template_use_btn.grid(row=0, column=0, padx=(0, 3), sticky=(tk.W, tk.E, tk.N, tk.S))

        self.template_delete_btn = ttk.Button(btn_frame, text="🗑️ Delete",
                                             command=self._delete_template, state='disabled')
        self.template_delete_btn.grid(row=0, column=1, padx=(3, 0), sticky=(tk.W, tk.E, tk.N, tk.S))

        # Add custom template section
        add_frame = ttk.LabelFrame(right_column, text="➕ Add Custom Template", padding="3")
        add_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N))
        add_frame.columnconfigure(1, weight=1)

        # Name field
        ttk.Label(add_frame, text="Name:", font=('Arial', 8)).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 8), pady=(0, 2))
        self.new_template_name = ttk.Entry(add_frame, font=('Arial', 8))
        self.new_template_name.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 2))

        # Description field
        ttk.Label(add_frame, text="Description:", font=('Arial', 8)).grid(
            row=1, column=0, sticky=tk.W, padx=(0, 8), pady=(0, 2))
        self.new_template_desc = ttk.Entry(add_frame, font=('Arial', 8))
        self.new_template_desc.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 2))

        # Command field
        ttk.Label(add_frame, text="Command:", font=('Arial', 8)).grid(
            row=2, column=0, sticky=(tk.W, tk.N), padx=(0, 8), pady=(0, 2))

        cmd_input_frame = ttk.Frame(add_frame)
        cmd_input_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(0, 2))
        cmd_input_frame.columnconfigure(0, weight=1)

        self.new_template_cmd = tk.Text(cmd_input_frame, height=2, wrap=tk.WORD,
                                       font=('Consolas', 8), padx=4, pady=3,
                                       relief=tk.SOLID, borderwidth=1)
        self.new_template_cmd.grid(row=0, column=0, sticky=(tk.W, tk.E))

        # Add button
        add_btn_frame = ttk.Frame(add_frame)
        add_btn_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(1, 0))

        ttk.Button(add_btn_frame, text="➕ Add Template", command=self._add_custom_template,
                  style='Accent.TButton').pack(side=tk.RIGHT)

        # Load templates
        self._refresh_template_list()
    
    def _create_ytdlp_section(self, parent):
        """Create yt-dlp executable path selection section"""
        ytdlp_label = ttk.Label(parent, text="yt-dlp Executable:", font=('Arial', 9, 'bold'))
        ytdlp_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 2))

        path_frame = ttk.Frame(parent)
        path_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        path_frame.columnconfigure(0, weight=1)

        self.yt_dlp_entry = ttk.Entry(path_frame, width=50)
        self.yt_dlp_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 3))
        ToolTip(self.yt_dlp_entry, "Path to yt-dlp.exe executable\nDownload from the 'Get yt-dlp' tab if you don't have it")

        self.yt_dlp_browse_btn = ttk.Button(path_frame, text="📁 Browse...", command=self.browse_yt_dlp)
        self.yt_dlp_browse_btn.grid(row=0, column=1, sticky=tk.W)
        ToolTip(self.yt_dlp_browse_btn, "Browse for yt-dlp.exe on your computer")

    def _create_url_section(self, parent):
        """Create video URL input section"""
        ttk.Label(parent, text="🔗 Video URL:", font=('Arial', 9, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 2))

        url_frame = ttk.Frame(parent)
        url_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        url_frame.columnconfigure(0, weight=1)

        self.url_entry = ttk.Entry(url_frame, width=50, font=('Arial', 9))
        self.url_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 3))
        ToolTip(self.url_entry, "Enter the URL of the video you want to download\nSupports YouTube, Vimeo, and many other sites")

        paste_btn = ttk.Button(url_frame, text="📋 Paste", command=self.paste_url)
        paste_btn.grid(row=0, column=1, padx=(0, 3))
        ToolTip(paste_btn, "Paste URL from clipboard")

        fetch_btn = ttk.Button(url_frame, text="ℹ️ Fetch Info", command=self.fetch_video_info)
        fetch_btn.grid(row=0, column=2)
        ToolTip(fetch_btn, "Fetch video information and thumbnail\n(Optional - helps preview before downloading)")

    def _create_metadata_section(self, parent):
        """Create video metadata display section"""
        # Metadata frame (initially hidden)
        self.metadata_frame = ttk.LabelFrame(parent, text="Video Information", padding="3")
        self.metadata_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        self.metadata_frame.columnconfigure(1, weight=1)

        # Thumbnail (left side)
        self.thumbnail_label = ttk.Label(self.metadata_frame)
        self.thumbnail_label.grid(row=0, column=0, rowspan=4, sticky=tk.NW, padx=(0, 5))

        # Info container (right side)
        info_frame = ttk.Frame(self.metadata_frame)
        info_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), rowspan=4)
        info_frame.columnconfigure(0, weight=1)

        # Title
        title_frame = ttk.Frame(info_frame)
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 1))
        title_frame.columnconfigure(1, weight=1)
        ttk.Label(title_frame, text="Title:", font=('Arial', 8, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.metadata_title = ttk.Label(title_frame, text="", wraplength=400, font=('Arial', 8))
        self.metadata_title.grid(row=0, column=1, sticky=tk.W, padx=(3, 0))

        # Duration
        duration_frame = ttk.Frame(info_frame)
        duration_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 1))
        duration_frame.columnconfigure(1, weight=1)
        ttk.Label(duration_frame, text="Duration:", font=('Arial', 8, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.metadata_duration = ttk.Label(duration_frame, text="", font=('Arial', 8))
        self.metadata_duration.grid(row=0, column=1, sticky=tk.W, padx=(3, 0))

        # Uploader
        uploader_frame = ttk.Frame(info_frame)
        uploader_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 1))
        uploader_frame.columnconfigure(1, weight=1)
        ttk.Label(uploader_frame, text="Uploader:", font=('Arial', 8, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.metadata_uploader = ttk.Label(uploader_frame, text="", font=('Arial', 8))
        self.metadata_uploader.grid(row=0, column=1, sticky=tk.W, padx=(3, 0))

        # Views
        views_frame = ttk.Frame(info_frame)
        views_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))
        views_frame.columnconfigure(1, weight=1)
        ttk.Label(views_frame, text="Views:", font=('Arial', 8, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.metadata_views = ttk.Label(views_frame, text="", font=('Arial', 8))
        self.metadata_views.grid(row=0, column=1, sticky=tk.W, padx=(3, 0))

        # Hide metadata frame initially
        self.metadata_frame.grid_remove()

    def _create_trim_section(self, parent):
        """Create trim/cut controls section"""
        # Trim frame (initially hidden)
        self.trim_frame = ttk.LabelFrame(parent, text="Trim Video (Optional)", padding="3")
        self.trim_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        self.trim_frame.columnconfigure(0, weight=0)

        # Enable trim checkbox
        self.trim_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.trim_frame, text="Enable trimming",
                       variable=self.trim_enabled,
                       command=self._toggle_trim_controls).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 2))

        # Time inputs frame (Start and End on same line)
        time_frame = ttk.Frame(self.trim_frame)
        time_frame.grid(row=1, column=0, sticky=tk.W)

        # Start time
        ttk.Label(time_frame, text="Start:", font=('Arial', 8)).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 3))
        self.trim_start_entry = ttk.Entry(time_frame, width=12, state='disabled')
        self.trim_start_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 8))
        self.trim_start_entry.insert(0, "00:00:00")

        # End time
        ttk.Label(time_frame, text="End:", font=('Arial', 8)).grid(
            row=0, column=2, sticky=tk.W, padx=(0, 3))
        self.trim_end_entry = ttk.Entry(time_frame, width=12, state='disabled')
        self.trim_end_entry.grid(row=0, column=3, sticky=tk.W)
        self.trim_end_entry.insert(0, "00:00:00")

        # Help text
        help_text = ttk.Label(self.trim_frame,
                             text="Format: HH:MM:SS",
                             font=('Arial', 7), foreground='gray')
        help_text.grid(row=2, column=0, sticky=tk.W, pady=(2, 0))

        # Hide trim frame initially
        self.trim_frame.grid_remove()

    def _create_output_section(self, parent):
        """Create output directory selection section"""
        ttk.Label(parent, text="📂 Output Directory:", font=('Arial', 9, 'bold')).grid(
            row=4, column=0, sticky=tk.W, pady=(0, 2))

        output_frame = ttk.Frame(parent)
        output_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        output_frame.columnconfigure(0, weight=1)

        self.output_entry = ttk.Entry(output_frame, width=50, font=('Arial', 9))
        self.output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 3))
        self.output_entry.insert(0, str(Path.home() / "Downloads"))
        ToolTip(self.output_entry, "Directory where downloaded files will be saved")

        browse_btn = ttk.Button(output_frame, text="📁 Browse...", command=self.browse_output)
        browse_btn.grid(row=0, column=1)
        ToolTip(browse_btn, "Select output directory")

    def _create_format_section(self, parent):
        """Create format selection section"""
        ttk.Label(parent, text="🎬 Format:", font=('Arial', 9, 'bold')).grid(
            row=6, column=0, sticky=tk.W, pady=(0, 2))

        format_frame = ttk.Frame(parent)
        format_frame.grid(row=7, column=0, sticky=tk.W, pady=(0, 8))

        self.format_var = tk.StringVar(value="mp4")
        mp4_radio = ttk.Radiobutton(format_frame, text="🎥 MP4 (Video)", variable=self.format_var,
                       value="mp4")
        mp4_radio.grid(row=0, column=0, padx=(0, 15))
        ToolTip(mp4_radio, "Download as video file (MP4 format)")

        mp3_radio = ttk.Radiobutton(format_frame, text="🎵 MP3 (Audio)", variable=self.format_var,
                       value="mp3")
        mp3_radio.grid(row=0, column=1)
        ToolTip(mp3_radio, "Extract and download audio only (MP3 format)")

    def _create_quality_section(self, parent):
        """Create quality selection section"""
        ttk.Label(parent, text="⭐ Quality:", font=('Arial', 9, 'bold')).grid(
            row=8, column=0, sticky=tk.W, pady=(0, 2))

        quality_frame = ttk.Frame(parent)
        quality_frame.grid(row=9, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        quality_frame.columnconfigure(0, weight=1)

        self.quality_var = tk.StringVar(value="best")
        quality_options = [
            ("Best Quality", "best"),
            ("1080p", "1080"),
            ("720p", "720"),
            ("480p", "480"),
            ("360p", "360"),
            ("Worst (smallest)", "worst")
        ]

        self.quality_combo = ttk.Combobox(quality_frame, textvariable=self.quality_var,
                                         state='readonly', width=25)
        self.quality_combo['values'] = [opt[0] for opt in quality_options]
        self.quality_combo.current(0)
        self.quality_combo.grid(row=0, column=0, sticky=(tk.W, tk.E))
        ToolTip(self.quality_combo, "Select video quality\nHigher quality = larger file size")

        # Store mapping of display names to values
        self.quality_mapping = {opt[0]: opt[1] for opt in quality_options}

    def _create_download_button(self, parent):
        """Create download button and progress bar"""
        # Progress bar frame (hidden initially)
        self.download_progress_frame = ttk.Frame(parent)
        self.download_progress_frame.grid(row=10, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        self.download_progress_frame.columnconfigure(0, weight=1)

        self.download_progress_label = ttk.Label(self.download_progress_frame, text="",
                                                 font=('Arial', 9))
        self.download_progress_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        self.download_progress_bar = ttk.Progressbar(self.download_progress_frame,
                                                     mode='indeterminate', length=400)
        self.download_progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # Initially hide progress
        self.download_progress_frame.grid_remove()

        # Download button
        self.download_btn = ttk.Button(parent, text="📥 Download",
                                       command=self.start_download, style='Accent.TButton')
        self.download_btn.grid(row=11, column=0, pady=(0, 5), sticky=(tk.W, tk.E))
        ToolTip(self.download_btn, "Start downloading the video with selected settings")
    
    def _create_output_log(self, parent):
        """Create output log section"""
        self.output_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, state='disabled')
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    def _create_status_bar(self, parent):
        """Create status bar"""
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(parent, textvariable=self.status_var, relief=tk.SUNKEN,
                              anchor=tk.W)
        status_bar.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
    
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

        # Update metadata display
        self.metadata_title.config(text=metadata.get('title', 'Unknown'))
        self.metadata_duration.config(
            text=MetadataFetcher.format_duration(metadata.get('duration', 0))
        )
        self.metadata_uploader.config(text=metadata.get('uploader', 'Unknown'))
        self.metadata_views.config(
            text=MetadataFetcher.format_number(metadata.get('view_count', 0))
        )

        # Load and display thumbnail
        thumbnail_url = metadata.get('thumbnail', '')
        if thumbnail_url:
            self._load_thumbnail(thumbnail_url)

        # Show metadata frame
        self.metadata_frame.grid()

        # Show trim frame
        self.trim_frame.grid()

        # Update end time in trim section to video duration
        duration_str = MetadataFetcher.format_duration(metadata.get('duration', 0))
        self.trim_end_entry.delete(0, tk.END)
        self.trim_end_entry.insert(0, duration_str)

        # Expand window to accommodate metadata
        self._resize_window_for_metadata()

        # Check if scrollbar is needed after showing metadata
        self.root.after(100, self._check_scrollbar_needed)

        self.status_var.set("Video information fetched successfully")
        self.log_message(f"✓ Video: {metadata.get('title', 'Unknown')}")
        self.log_message(f"  Duration: {MetadataFetcher.format_duration(metadata.get('duration', 0))}")
        self.log_message(f"  Uploader: {metadata.get('uploader', 'Unknown')}")

    def _on_metadata_error(self, error_msg):
        """Handle metadata fetch error"""
        self.status_var.set("Failed to fetch video information")
        self.log_message(f"✗ Error: {error_msg}")
        messagebox.showerror("Fetch Error", f"Failed to fetch video information:\n{error_msg}")

    def _toggle_trim_controls(self):
        """Toggle trim control states"""
        if self.trim_enabled.get():
            self.trim_start_entry.config(state='normal')
            self.trim_end_entry.config(state='normal')
        else:
            self.trim_start_entry.config(state='disabled')
            self.trim_end_entry.config(state='disabled')

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

        # Disable download button during download
        self.download_btn.configure(state='disabled')
        self.status_var.set("Downloading...")

        # Show and start progress bar
        self.download_progress_frame.grid()
        self.download_progress_label.config(text="Preparing download...")
        self.download_progress_bar.start(10)  # Indeterminate mode animation

        # Switch to log tab
        self.notebook.select(self.log_tab)

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

            # Validate time format
            if not self._validate_time_format(trim_start) or not self._validate_time_format(trim_end):
                messagebox.showerror("Invalid Time", "Please use HH:MM:SS format for trim times")
                self.download_btn.configure(state='normal')
                self.status_var.set("Ready")
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
            on_error=self._on_download_error
        )

    def _start_template_download(self):
        """Start download using custom template"""
        import subprocess
        import threading

        # Disable download button during download
        self.download_btn.configure(state='disabled')
        self.status_var.set("Downloading with template...")

        # Show and start progress bar
        self.download_progress_frame.grid()
        self.download_progress_label.config(text="Downloading with custom template...")
        self.download_progress_bar.start(10)

        # Switch to log tab
        self.notebook.select(self.log_tab)

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
                    bufsize=1
                )

                # Read output line by line
                for line in process.stdout:
                    self.log_message(line.rstrip())

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
    
    def _on_download_complete(self):
        """Callback when download completes successfully"""
        self.status_var.set("Download completed!")
        self.download_btn.configure(state='normal')

        # Stop and hide progress bar
        self.download_progress_bar.stop()
        self.download_progress_label.config(text="✓ Download completed!")
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

        # Stop and hide progress bar
        self.download_progress_bar.stop()
        self.download_progress_label.config(text="✗ Download failed!")
        self.root.after(2000, self.download_progress_frame.grid_remove)

        messagebox.showerror("Error", f"Download failed: {error_msg}")

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

            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(image)

            # Keep a reference to prevent garbage collection
            self.thumbnail_photo = photo

            # Display in label
            self.thumbnail_label.config(image=photo)

            self.log_message("✓ Thumbnail loaded")

        except Exception as e:
            self.log_message(f"⚠ Could not load thumbnail: {str(e)}")

    def _check_scrollbar_needed(self):
        """Check if scrollbar is needed and show/hide accordingly"""
        try:
            # Get the canvas height and content height
            canvas_height = self.download_canvas.winfo_height()
            content_height = self.download_tab.winfo_reqheight()

            # Show scrollbar if content is taller than canvas
            if content_height > canvas_height and not self.scrollbar_visible:
                self.download_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, before=self.download_canvas)
                self.scrollbar_visible = True
            elif content_height <= canvas_height and self.scrollbar_visible:
                self.download_scrollbar.pack_forget()
                self.scrollbar_visible = False
        except:
            pass  # Ignore errors during initialization

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
        self.ytdlp_progress_bar['value'] = 0
        self.ytdlp_progress_label.config(text=f"Preparing to download {version_type} version...")

        # Switch to log tab
        self.notebook.select(self.log_tab)

        # Clear log
        self.output_text.configure(state='normal')
        self.output_text.delete(1.0, tk.END)
        self.output_text.configure(state='disabled')

        def on_progress(downloaded, total):
            if total > 0:
                percent = (downloaded / total) * 100
                self.ytdlp_progress_bar['value'] = percent
                self.ytdlp_progress_label.config(
                    text=f"Downloading: {downloaded:,} / {total:,} bytes ({percent:.1f}%)"
                )

        def on_complete(file_path):
            self.ytdlp_download_btn.configure(state='normal')
            self.ytdlp_progress_label.config(text="Download completed!")
            self.status_var.set("yt-dlp downloaded successfully")

            # Set the path in the main yt-dlp entry
            self.yt_dlp_entry.delete(0, tk.END)
            self.yt_dlp_entry.insert(0, file_path)
            self.config.set('yt_dlp_path', file_path)

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
            self.template_name_label.config(text=template['name'])
            self.template_desc_label.config(text=template['description'])

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
                self.notebook.select(self.download_canvas_frame)

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
                    self.template_name_label.config(text="")
                    self.template_desc_label.config(text="")
                    self.template_cmd_text.delete('1.0', tk.END)
                    self.template_use_btn.configure(state='disabled')
                    self.template_delete_btn.configure(state='disabled')
                else:
                    messagebox.showerror("Error", "Failed to delete template")

