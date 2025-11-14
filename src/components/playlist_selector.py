"""Playlist selector dialog for choosing videos from a playlist"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, List, Dict, Any


class PlaylistSelector:
    """Dialog for selecting videos from a playlist"""
    
    def __init__(self, parent, playlist_info: Dict[str, Any], on_select: Callable):
        """
        Initialize playlist selector dialog
        
        Args:
            parent: Parent window
            playlist_info: Dictionary with playlist data (videos, playlist_title, n_entries)
            on_select: Callback function with selected videos
        """
        self.parent = parent
        self.playlist_info = playlist_info
        self.on_select = on_select
        self.selected_videos = []
        self.select_all_var = tk.BooleanVar(value=False)
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
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
        header_frame = ttk.Frame(self.dialog)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(header_frame, text=f"Playlist: {self.playlist_info.get('playlist_title', 'Playlist')}",
                 font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Total videos: {self.playlist_info.get('n_entries', 0)}",
                 font=('Arial', 9), foreground='gray').pack(anchor=tk.W)
        
        # Control buttons
        control_frame = ttk.Frame(self.dialog)
        control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Checkbutton(control_frame, text="Select All",
                       variable=self.select_all_var,
                       command=self._toggle_select_all).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(control_frame, text="Clear All",
                  command=self._clear_all).pack(side=tk.LEFT)
        
        # Video list with scrollbar
        list_frame = ttk.Frame(self.dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.video_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                       selectmode=tk.MULTIPLE, height=15)
        self.video_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.video_listbox.yview)
        
        # Populate listbox
        videos = self.playlist_info.get('videos', [])
        for idx, video in enumerate(videos):
            title = video.get('title', 'Unknown')
            self.video_listbox.insert(tk.END, f"{idx+1}. {title}")
        
        # Button frame
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        button_frame.columnconfigure(0, weight=1)
        
        ttk.Button(button_frame, text="✓ Download Selected",
                  command=self._on_confirm).grid(row=0, column=0, sticky=tk.E, padx=(0, 5))
        ttk.Button(button_frame, text="✗ Cancel",
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

