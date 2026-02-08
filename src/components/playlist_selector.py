"""Playlist selector dialog for choosing videos from a playlist"""

import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional, List, Dict, Any


class PlaylistSelector:
    """Dialog for selecting videos from a playlist"""

    def __init__(self, parent, playlist_info: Dict[str, Any], on_select: Callable,
                 initial_selected_ids: Optional[set] = None):
        """
        Initialize playlist selector dialog

        Args:
            parent: Parent window
            playlist_info: Dictionary with playlist data (videos, playlist_title, n_entries)
            on_select: Callback function with selected videos
            initial_selected_ids: Optional set of video IDs to pre-select
        """
        self.parent = parent
        self.playlist_info = playlist_info
        self.on_select = on_select
        self.selected_videos = []
        self.select_all_var = tk.BooleanVar(value=False)
        self.initial_selected_ids = initial_selected_ids or set()

        # Create dialog window
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(f"Select Videos - {playlist_info.get('playlist_title', 'Playlist')}")
        self.dialog.geometry("700x500")
        self.dialog.resizable(True, True)

        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

        # Center dialog on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create dialog widgets"""
        # Header
        header_frame = ctk.CTkFrame(self.dialog)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ctk.CTkLabel(header_frame, text=f"Playlist: {self.playlist_info.get('playlist_title', 'Playlist')}",
                 font=('Arial', 13, 'bold')).pack(anchor=tk.W, padx=10, pady=(5, 0))
        ctk.CTkLabel(header_frame, text=f"Total videos: {self.playlist_info.get('n_entries', 0)}",
                 font=('Arial', 12), text_color='gray').pack(anchor=tk.W, padx=10, pady=(0, 5))

        # Control buttons
        control_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ctk.CTkCheckBox(control_frame, text="Select All",
                       variable=self.select_all_var,
                       command=self._toggle_select_all,
                       font=('Arial', 13),
                       checkbox_width=22, checkbox_height=22).pack(side=tk.LEFT, padx=(0, 10))

        ctk.CTkButton(control_frame, text="Clear All",
                  command=self._clear_all, width=80).pack(side=tk.LEFT)

        # Video list with checkboxes
        list_frame = ctk.CTkFrame(self.dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.video_scroll = ctk.CTkScrollableFrame(list_frame)
        self.video_scroll.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.video_scroll.columnconfigure(0, weight=1)

        self.video_vars = []
        self.videos = self.playlist_info.get('videos', [])

        # Defer population so the dialog can render first (important for large playlists)
        self.dialog.after(0, self._populate_videos)

        # Button frame
        button_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        button_frame.columnconfigure(0, weight=1)

        ctk.CTkButton(button_frame, text="✓ Download Selected",
                  command=self._on_confirm).grid(row=0, column=0, sticky=tk.E, padx=(0, 5))
        ctk.CTkButton(button_frame, text="✗ Cancel",
                  command=self.dialog.destroy).grid(row=0, column=1, sticky=tk.E)

    def _populate_videos(self):
        """Populate checkbox list and pre-select videos if initial_selected_ids provided"""
        for idx, video in enumerate(self.videos):
            title = video.get('title', 'Unknown')
            var = tk.BooleanVar(value=False)

            # Pre-select if this video was previously selected
            video_id = video.get('id', '')
            if video_id and video_id in self.initial_selected_ids:
                var.set(True)

            checkbox = ctk.CTkCheckBox(
                self.video_scroll,
                text=f"{idx + 1}. {title}",
                variable=var,
                font=('Arial', 13),
                checkbox_width=22, checkbox_height=22
            )
            checkbox.grid(row=idx, column=0, sticky=tk.W, pady=2)
            self.video_vars.append(var)

        # Update select all checkbox state
        if len(self.initial_selected_ids) == len(self.videos) and len(self.videos) > 0:
            self.select_all_var.set(True)
    
    def _toggle_select_all(self):
        """Toggle select all videos"""
        if self.select_all_var.get():
            for var in self.video_vars:
                var.set(True)
        else:
            for var in self.video_vars:
                var.set(False)
    
    def _clear_all(self):
        """Clear all selections"""
        for var in self.video_vars:
            var.set(False)
        self.select_all_var.set(False)
    
    def _on_confirm(self):
        """Handle confirm button"""
        selections = [idx for idx, var in enumerate(self.video_vars) if var.get()]
        if not selections:
            return
        
        self.selected_videos = [self.videos[i] for i in selections]
        
        # Call callback with selected videos
        self.on_select(self.selected_videos)
        
        self.dialog.destroy()

