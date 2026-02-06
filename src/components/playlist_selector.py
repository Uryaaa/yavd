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
                       command=self._toggle_select_all).pack(side=tk.LEFT, padx=(0, 10))

        ctk.CTkButton(control_frame, text="Clear All",
                  command=self._clear_all, width=80).pack(side=tk.LEFT)

        # Video list with scrollbar
        list_frame = ctk.CTkFrame(self.dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = ctk.CTkScrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.video_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                       selectmode=tk.MULTIPLE, height=15,
                                       font=('Arial', 12))
        self.video_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.configure(command=self.video_listbox.yview)

        # Populate listbox and pre-select videos if initial_selected_ids provided
        videos = self.playlist_info.get('videos', [])
        for idx, video in enumerate(videos):
            title = video.get('title', 'Unknown')
            self.video_listbox.insert(tk.END, f"{idx+1}. {title}")

            # Pre-select if this video was previously selected
            video_id = video.get('id', '')
            if video_id and video_id in self.initial_selected_ids:
                self.video_listbox.select_set(idx)

        # Update select all checkbox state
        if len(self.initial_selected_ids) == len(videos) and len(videos) > 0:
            self.select_all_var.set(True)

        # Button frame
        button_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        button_frame.columnconfigure(0, weight=1)

        ctk.CTkButton(button_frame, text="✓ Download Selected",
                  command=self._on_confirm).grid(row=0, column=0, sticky=tk.E, padx=(0, 5))
        ctk.CTkButton(button_frame, text="✗ Cancel",
                  command=self.dialog.destroy).grid(row=0, column=1, sticky=tk.E)
    
    def _toggle_select_all(self):
        """Toggle select all videos"""
        if self.select_all_var.get():
            self.video_listbox.select_set(0, tk.END)
        else:
            self.video_listbox.select_clear(0, tk.END)
    
    def _clear_all(self):
        """Clear all selections"""
        self.video_listbox.select_clear(0, tk.END)
        self.select_all_var.set(False)
    
    def _on_confirm(self):
        """Handle confirm button"""
        selections = self.video_listbox.curselection()
        if not selections:
            return
        
        videos = self.playlist_info.get('videos', [])
        self.selected_videos = [videos[i] for i in selections]
        
        # Call callback with selected videos
        self.on_select(self.selected_videos)
        
        self.dialog.destroy()

