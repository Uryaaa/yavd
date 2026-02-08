"""UI construction helpers for MainWindow."""

import tkinter as tk
import customtkinter as ctk
from pathlib import Path

from .context_menu import ContextMenu
from .main_window_time_entry import TimeEntry


class MainWindowUI:
    def _apply_tk_widget_theme(self, widget, kind: str):
        """Apply light/dark colors to tk widgets for consistency."""
        mode = ctk.get_appearance_mode()
        is_dark = mode == "Dark"

        if kind == "listbox":
            bg = "#1F242B" if is_dark else "#FFFFFF"
            fg = "#E6E9EF" if is_dark else "#1F2937"
            select_bg = "#2F6FED"
            select_fg = "#FFFFFF"
            widget.configure(
                bg=bg,
                fg=fg,
                selectbackground=select_bg,
                selectforeground=select_fg
            )
        elif kind == "text":
            bg = "#20262E" if is_dark else "#FFFFFF"
            fg = "#E6E9EF" if is_dark else "#1F2937"
            widget.configure(bg=bg, fg=fg, insertbackground=fg)

    def _layout_option_buttons(self, frame, widgets, min_col_width=140):
        """Lay out option widgets responsively based on available width."""
        if not widgets or not frame or not frame.winfo_exists():
            return

        width = frame.winfo_width()
        try:
            if frame.master and frame.master.winfo_exists():
                master_width = frame.master.winfo_width()
                if master_width > 1:
                    width = min(width, master_width)
        except Exception:
            pass
        if width <= 1:
            if frame.winfo_exists():
                self._schedule_option_layout(frame, widgets, min_col_width)
            return

        max_req_width = 0
        for widget in widgets:
            try:
                if widget and widget.winfo_exists():
                    max_req_width = max(max_req_width, widget.winfo_reqwidth())
            except Exception:
                pass

        col_width = max(min_col_width, max_req_width + 12)
        columns = max(1, width // col_width)

        for widget in widgets:
            try:
                if widget and widget.winfo_exists():
                    widget.grid_forget()
            except Exception:
                pass

        visible_widgets = []
        for widget in widgets:
            try:
                if widget and widget.winfo_exists():
                    visible_widgets.append(widget)
            except Exception:
                pass

        for idx, widget in enumerate(visible_widgets):
            row = idx // columns
            col = idx % columns
            try:
                widget.grid(row=row, column=col, sticky=tk.W, padx=(0, 10), pady=2)
            except Exception:
                pass

        for col in range(columns):
            frame.grid_columnconfigure(col, weight=0)

    def _schedule_option_layout(self, frame, widgets, min_col_width=140, delay=80):
        """Debounce layout updates to avoid resize lag."""
        if not frame or not frame.winfo_exists():
            return
        after_id = getattr(frame, "_layout_after_id", None)
        if after_id:
            try:
                frame.after_cancel(after_id)
            except Exception:
                pass
        frame._layout_after_id = frame.after(
            delay,
            lambda: self._layout_option_buttons(frame, widgets, min_col_width)
        )
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

        # Place separator directly below the tab buttons (inside tabview)
        self._tab_sep = ctk.CTkFrame(self.tabview, height=2, fg_color=("#B5BEC9", "#3A4452"))

        def _place_tab_separator():
            try:
                self.tabview.update_idletasks()
                segmented = self.tabview._segmented_button
                y = segmented.winfo_height() + 2
                self._tab_sep.place(x=0, y=y, relwidth=1)
            except Exception:
                pass

        def _poll_tab_separator():
            _place_tab_separator()
            self.tabview.after(300, _poll_tab_separator)

        self.tabview.after(0, _poll_tab_separator)

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
        self.ytdlp_version_vars = {
            "stable": tk.BooleanVar(value=True),
            "nightly": tk.BooleanVar(value=False),
            "master": tk.BooleanVar(value=False),
        }

        def select_ytdlp_version(version: str):
            for key, var in self.ytdlp_version_vars.items():
                var.set(key == version)
            self.ytdlp_version_var.set(version)

        ctk.CTkCheckBox(
            version_frame,
            text="Stable - Recommended for most users",
            variable=self.ytdlp_version_vars["stable"],
            command=lambda: select_ytdlp_version("stable"),
            checkbox_width=22, checkbox_height=22,
            font=('Arial', 13)
        ).grid(row=1, column=0, sticky=tk.W, pady=2, padx=10)

        ctk.CTkCheckBox(
            version_frame,
            text="Nightly - Latest features and fixes",
            variable=self.ytdlp_version_vars["nightly"],
            command=lambda: select_ytdlp_version("nightly"),
            checkbox_width=22, checkbox_height=22,
            font=('Arial', 13)
        ).grid(row=2, column=0, sticky=tk.W, pady=2, padx=10)

        ctk.CTkCheckBox(
            version_frame,
            text="Master - Bleeding edge (may be unstable)",
            variable=self.ytdlp_version_vars["master"],
            command=lambda: select_ytdlp_version("master"),
            checkbox_width=22, checkbox_height=22,
            font=('Arial', 13)
        ).grid(row=3, column=0, sticky=tk.W, pady=(2, 10), padx=10)

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

        # Build selection
        build_frame = ctk.CTkFrame(self.ffmpeg_tab)
        build_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10), padx=10)
        build_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(build_frame, text="Select Build", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(5, 5), padx=10)

        self.ffmpeg_variant_var = tk.StringVar(value="gpl")
        self.ffmpeg_variant_vars = {
            "gpl": tk.BooleanVar(value=True),
            "lgpl": tk.BooleanVar(value=False),
            "shared": tk.BooleanVar(value=False),
        }

        def select_variant(variant: str):
            for key, var in self.ffmpeg_variant_vars.items():
                var.set(key == variant)
            self.ffmpeg_variant_var.set(variant)

        ctk.CTkCheckBox(
            build_frame,
            text="GPL - Recommended (static)",
            variable=self.ffmpeg_variant_vars["gpl"],
            command=lambda: select_variant("gpl"),
            checkbox_width=22, checkbox_height=22,
            font=('Arial', 13)
        ).grid(row=1, column=0, sticky=tk.W, pady=2, padx=10)

        ctk.CTkCheckBox(
            build_frame,
            text="LGPL - Smaller (static)",
            variable=self.ffmpeg_variant_vars["lgpl"],
            command=lambda: select_variant("lgpl"),
            checkbox_width=22, checkbox_height=22,
            font=('Arial', 13)
        ).grid(row=2, column=0, sticky=tk.W, pady=2, padx=10)

        ctk.CTkCheckBox(
            build_frame,
            text="GPL Shared - Requires DLLs",
            variable=self.ffmpeg_variant_vars["shared"],
            command=lambda: select_variant("shared"),
            checkbox_width=22, checkbox_height=22,
            font=('Arial', 13)
        ).grid(row=3, column=0, sticky=tk.W, pady=(2, 8), padx=10)

        # Output location
        location_frame = ctk.CTkFrame(self.ffmpeg_tab)
        location_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10), padx=10)
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
        self.ffmpeg_progress_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
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
        self.ffmpeg_download_btn.grid(row=5, column=0, pady=(0, 10), sticky=(tk.W, tk.E))

        # Info text
        info_text = ("After downloading, you can use FFmpeg for advanced video processing.\n"
                    "If you already have FFmpeg, it will be automatically detected.")
        ctk.CTkLabel(self.ffmpeg_tab, text=info_text, font=('Arial', 11),
                 text_color='gray').grid(row=6, column=0, sticky=tk.W)

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

        # Scrollable list for templates (CTk widgets adapt to theme)
        self.template_list_frame = ctk.CTkScrollableFrame(list_frame, height=180)
        self.template_list_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=(0, 5))
        self.template_list_frame.columnconfigure(0, weight=1)
        self.template_item_buttons = []

        # RIGHT COLUMN: Template details and actions (scrollable for smaller windows)
        self.templates_right_scroll = ctk.CTkScrollableFrame(content_frame)
        self.templates_right_scroll.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(3, 0))
        self.templates_right_scroll.columnconfigure(0, weight=1)

        # Template details frame with scrollable content
        details_outer_frame = ctk.CTkFrame(self.templates_right_scroll)
        details_outer_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 6))
        details_outer_frame.columnconfigure(0, weight=1)
        details_outer_frame.rowconfigure(0, weight=0)  # Label row - no expand
        details_outer_frame.rowconfigure(1, weight=1)  # Scrollable content - expand

        ctk.CTkLabel(details_outer_frame, text="📝 Template Details", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(5, 5), padx=5)

        # Template details container (use parent scroll only to avoid nested scrollbars)
        self.template_details_frame = ctk.CTkFrame(details_outer_frame)
        self.template_details_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=(0, 5))
        self.template_details_frame.columnconfigure(0, weight=1)

        # Name
        ctk.CTkLabel(self.template_details_frame, text="Name:", font=('Arial', 11, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 0))
        self.template_name_label = ctk.CTkLabel(self.template_details_frame, text="Select a template to view details",
                                            font=('Arial', 11), text_color='gray')
        self.template_name_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 2))

        # Description
        ctk.CTkLabel(self.template_details_frame, text="Description:", font=('Arial', 11, 'bold')).grid(
            row=2, column=0, sticky=tk.W, pady=(0, 0))
        self.template_desc_label = ctk.CTkLabel(self.template_details_frame, text="",
                                            font=('Arial', 11), wraplength=400, justify=tk.LEFT)
        self.template_desc_label.grid(row=3, column=0, sticky=tk.W, pady=(0, 2))

        # Command
        ctk.CTkLabel(self.template_details_frame, text="Command:", font=('Arial', 11, 'bold')).grid(
            row=4, column=0, sticky=tk.W, pady=(0, 0))

        cmd_frame = ctk.CTkFrame(self.template_details_frame)
        cmd_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 2))
        cmd_frame.columnconfigure(0, weight=1)

        self.template_cmd_text = ctk.CTkTextbox(cmd_frame, height=50, wrap=tk.WORD)
        self.template_cmd_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.template_cmd_text.configure(state="disabled")
        ContextMenu(self.template_cmd_text, read_only=True)

        sep_color = ("#D3D9E1", "#2A313B")
        sep_1 = ctk.CTkFrame(self.templates_right_scroll, height=1, fg_color=sep_color)
        sep_1.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=(2, 6))

        # Action buttons (outside canvas, in right_column directly)
        btn_frame = ctk.CTkFrame(self.templates_right_scroll)
        btn_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(6, 6))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self.template_use_btn = ctk.CTkButton(btn_frame, text="✓ Use Template",
                                          command=self._use_template, state='disabled')
        self.template_use_btn.grid(row=0, column=0, padx=(5, 3), pady=5, sticky=(tk.W, tk.E))

        self.template_delete_btn = ctk.CTkButton(btn_frame, text="🗑️ Delete",
                                             command=self._delete_template, state='disabled')
        self.template_delete_btn.grid(row=0, column=1, padx=(3, 5), pady=5, sticky=(tk.W, tk.E))

        sep_2 = ctk.CTkFrame(self.templates_right_scroll, height=1, fg_color=sep_color)
        sep_2.grid(row=3, column=0, sticky=(tk.W, tk.E), padx=5, pady=(4, 6))

        # Add custom template section
        add_frame = ctk.CTkFrame(self.templates_right_scroll)
        add_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(4, 0))
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

        self.new_template_cmd = ctk.CTkTextbox(cmd_input_frame, height=80, wrap=tk.WORD)
        self.new_template_cmd.grid(row=0, column=0, sticky=(tk.W, tk.E))
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
        ytdlp_label.grid(row=0, column=0, sticky=tk.W, pady=(4, 2), padx=6)

        path_frame = ctk.CTkFrame(parent)
        path_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 8), padx=6)
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
        self.thumbnail_label.grid(row=1, column=0, rowspan=4, sticky=tk.NW, padx=(5, 5), pady=(6, 5))

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
        sep_color = ("#B5BEC9", "#3A4452")
        sep1 = ctk.CTkFrame(info_frame, height=1, fg_color=sep_color)
        sep1.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(2, 2))

        duration_frame = ctk.CTkFrame(info_frame)
        duration_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 1))
        duration_frame.columnconfigure(1, weight=1)
        ctk.CTkLabel(duration_frame, text="Duration:", font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.metadata_duration = ctk.CTkLabel(duration_frame, text="", font=('Arial', 11))
        self.metadata_duration.grid(row=0, column=1, sticky=tk.W, padx=(3, 0))

        # Uploader
        sep2 = ctk.CTkFrame(info_frame, height=1, fg_color=sep_color)
        sep2.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(2, 2))

        uploader_frame = ctk.CTkFrame(info_frame)
        uploader_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 1))
        uploader_frame.columnconfigure(1, weight=1)
        ctk.CTkLabel(uploader_frame, text="Uploader:", font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.metadata_uploader = ctk.CTkLabel(uploader_frame, text="", font=('Arial', 11))
        self.metadata_uploader.grid(row=0, column=1, sticky=tk.W, padx=(3, 0))

        # Views
        sep3 = ctk.CTkFrame(info_frame, height=1, fg_color=sep_color)
        sep3.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(2, 2))

        views_frame = ctk.CTkFrame(info_frame)
        views_frame.grid(row=6, column=0, sticky=(tk.W, tk.E))
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
                       command=self._toggle_trim_controls,
                       checkbox_width=22, checkbox_height=22).grid(
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
        self.convert_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(self.convert_frame, text="🔄 Remux", font=('Arial', 13, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=(5, 5), padx=5)

        # Enable convert checkbox
        self.convert_enabled = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.convert_frame, text="Enable remuxing",
                       variable=self.convert_enabled,
                       command=self._toggle_convert_controls,
                       checkbox_width=22, checkbox_height=22).grid(
            row=1, column=0, sticky=tk.W, pady=(0, 5), padx=5)

        # Format buttons frame
        self.convert_format_frame = ctk.CTkFrame(self.convert_frame, fg_color="transparent")
        self.convert_format_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=5, pady=(0, 5))
        self.convert_format_frame.columnconfigure(0, weight=1)

        # Convert format variable
        self.convert_format_var = tk.StringVar(value="mp4")

        # Video formats
        self.video_convert_formats = ['mp4', 'mkv', 'avi', 'mov', 'webm', 'flv', 'gif']
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
            formats = list(self.audio_convert_formats)
        else:
            formats = list(self.video_convert_formats)

        self.convert_format_vars = {}
        self.convert_format_checkboxes = []

        def select_convert_format(fmt: str):
            for key, var in self.convert_format_vars.items():
                var.set(key == fmt)
            self.convert_format_var.set(fmt)

        # Create checkbox buttons (exclusive selection)
        for fmt in formats:
            state = 'normal' if self.convert_enabled.get() else 'disabled'
            var = tk.BooleanVar(value=False)
            checkbox = ctk.CTkCheckBox(
                self.convert_format_frame,
                text=fmt.upper(),
                variable=var,
                command=lambda f=fmt: select_convert_format(f),
                state=state,
                checkbox_width=22, checkbox_height=22
            )
            self.convert_format_checkboxes.append(checkbox)
            self.convert_format_vars[fmt] = var

        self._schedule_option_layout(self.convert_format_frame, self.convert_format_checkboxes, min_col_width=120)

        if not getattr(self, "_convert_format_bound", False):
            self.convert_format_frame.bind(
                "<Configure>",
                lambda e: self._schedule_option_layout(
                    self.convert_format_frame,
                    self.convert_format_checkboxes,
                    min_col_width=120
                )
            )
            self._convert_format_bound = True

        # Set default value
        if formats:
            select_convert_format(formats[0])

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
        mode_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 5), padx=5)
        mode_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(mode_frame, text="Mode:", font=('Arial', 11, 'bold')).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 8))

        self.mode_options_frame = ctk.CTkFrame(mode_frame, fg_color="transparent")
        self.mode_options_frame.grid(row=0, column=1, sticky=(tk.W, tk.E))

        self.mode_var = tk.StringVar(value="auto")
        self.mode_vars = {
            "video": tk.BooleanVar(value=False),
            "audio": tk.BooleanVar(value=False),
            "auto": tk.BooleanVar(value=True),
        }

        def select_mode(mode: str):
            for key, var in self.mode_vars.items():
                var.set(key == mode)
            self.mode_var.set(mode)
            self._on_mode_changed()

        self.mode_checkboxes = []
        self.mode_checkboxes.append(ctk.CTkCheckBox(
            self.mode_options_frame,
            text="🎥 Video",
            variable=self.mode_vars["video"],
            command=lambda: select_mode("video"),
            checkbox_width=22, checkbox_height=22
        ))
        self.mode_checkboxes.append(ctk.CTkCheckBox(
            self.mode_options_frame,
            text="🎵 Audio Only",
            variable=self.mode_vars["audio"],
            command=lambda: select_mode("audio"),
            checkbox_width=22, checkbox_height=22
        ))
        self.mode_checkboxes.append(ctk.CTkCheckBox(
            self.mode_options_frame,
            text="⚙️ Auto",
            variable=self.mode_vars["auto"],
            command=lambda: select_mode("auto"),
            checkbox_width=22, checkbox_height=22
        ))

        self._schedule_option_layout(self.mode_options_frame, self.mode_checkboxes, min_col_width=160)
        self.mode_options_frame.bind(
            "<Configure>",
            lambda e: self._schedule_option_layout(self.mode_options_frame, self.mode_checkboxes, min_col_width=160)
        )

        # Format selection
        format_frame = ctk.CTkFrame(self.format_label_frame)
        format_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 5), padx=5)
        format_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(format_frame, text="Format:", font=('Arial', 11, 'bold')).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 8))

        self.format_var = tk.StringVar(value="mp4")
        self.format_radios = []
        self.format_radio_frame = ctk.CTkFrame(format_frame, fg_color="transparent")
        self.format_radio_frame.grid(row=0, column=1, sticky=(tk.W, tk.E))
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
        status_frame = ctk.CTkFrame(parent, fg_color="transparent")
        status_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(5, 0), padx=5)
        status_frame.columnconfigure(0, weight=1)
        status_frame.columnconfigure(1, weight=0)

        sep_color = ("#B5BEC9", "#3A4452")
        sep = ctk.CTkFrame(status_frame, height=2, fg_color=sep_color)
        sep.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 4))

        status_bar = ctk.CTkLabel(status_frame, textvariable=self.status_var, anchor=tk.W)
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        def update_theme_button_text():
            mode = ctk.get_appearance_mode()
            if mode == "Dark":
                self.theme_toggle_btn.configure(text="Light Mode")
            else:
                self.theme_toggle_btn.configure(text="Dark Mode")

        def toggle_theme():
            mode = ctk.get_appearance_mode()
            new_mode = "light" if mode == "Dark" else "dark"
            ctk.set_appearance_mode(new_mode)
            if hasattr(self, "config"):
                self.config.set("appearance_mode", new_mode)
            update_theme_button_text()

        self.theme_toggle_btn = ctk.CTkButton(status_frame, text="", width=110, command=toggle_theme)
        self.theme_toggle_btn.grid(row=1, column=1, padx=(8, 0))
        update_theme_button_text()
