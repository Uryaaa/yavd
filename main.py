"""
yt-dlp GUI Downloader
Main entry point for the application
"""

import tkinter as tk
from src.components import MainWindow


def main():
    """Initialize and run the application"""
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
