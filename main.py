"""
yt-dlp GUI Downloader
Main entry point for the application
"""

import customtkinter as ctk
from src.components import MainWindow


def main():
    """Initialize and run the application"""
    # Set appearance mode and color theme
    ctk.set_appearance_mode("system")  # Modes: "system" (default), "dark", "light"
    ctk.set_default_color_theme("blue")  # Themes: "blue" (default), "green", "dark-blue"

    root = ctk.CTk()
    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
