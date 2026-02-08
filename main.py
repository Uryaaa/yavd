"""
yt-dlp GUI Downloader
Main entry point for the application
"""

import customtkinter as ctk
from pathlib import Path
from src.config import ConfigManager
from src.components import MainWindow


def main():
    """Initialize and run the application"""
    # Set appearance mode and color theme
    config = ConfigManager()
    appearance_mode = config.get("appearance_mode", "system")
    ctk.set_appearance_mode(appearance_mode)  # Modes: "system" (default), "dark", "light"
    theme_path = Path(__file__).parent / "src" / "themes" / "yav_theme.json"
    if theme_path.exists():
        ctk.set_default_color_theme(str(theme_path))
    else:
        ctk.set_default_color_theme("blue")  # Fallback

    # Slightly increase overall UI scale for readability
    ctk.set_widget_scaling(1.08)

    root = ctk.CTk()
    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
