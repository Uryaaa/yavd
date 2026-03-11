"""Tooling-related handlers for MainWindow (yt-dlp, FFmpeg, templates)."""

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk


class MainWindowTools:
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
        variant = self.ffmpeg_variant_var.get() if hasattr(self, "ffmpeg_variant_var") else "gpl"

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

            # Persist ffmpeg path for later use
            if hasattr(self, "config"):
                self.config.set('ffmpeg_path', file_path)

            # Hide progress bar after 2 seconds
            self.root.after(2000, self.ffmpeg_progress_frame.grid_remove)

            if hasattr(self, "_refresh_tool_status"):
                self._refresh_tool_status()

            messagebox.showinfo("Success", f"FFmpeg downloaded successfully!\n\nSaved to:\n{file_path}")

        def on_error(error_msg):
            self.ffmpeg_download_btn.configure(state='normal')
            self.ffmpeg_progress_frame.grid_remove()
            self.status_var.set("FFmpeg download failed")
            messagebox.showerror("Download Error", f"Failed to download FFmpeg:\n{error_msg}")

        # Start download
        self.ffmpeg_downloader.download(
            output_path=save_path,
            build_variant=variant,
            on_progress=on_progress,
            on_log=self.log_message,
            on_complete=on_complete,
            on_error=on_error
        )

    # Template Tab Methods

    def _refresh_template_list(self):
        """Refresh the template listbox"""
        # Clear existing items
        for child in self.template_list_frame.winfo_children():
            child.destroy()
        self.template_item_buttons = []
        self.selected_template_index = None

        # Disable buttons until selection
        self.template_use_btn.configure(state='disabled')
        self.template_delete_btn.configure(state='disabled')

        templates = self.template_manager.get_all_templates()
        for idx, template in enumerate(templates):
            prefix = "[Preset] " if template.get('is_preset', False) else "[Custom] "
            btn = ctk.CTkButton(
                self.template_list_frame,
                text=prefix + template['name'],
                anchor="w",
                fg_color="transparent",
                hover_color=("#2F6FED", "#3B82F6"),
                text_color=("#1F2937", "#E6E9EF"),
                command=lambda i=idx: self._on_template_select(i)
            )
            btn.grid(row=idx, column=0, sticky=(tk.W, tk.E), padx=4, pady=2)
            self.template_item_buttons.append(btn)

    def _on_template_select(self, index):
        """Handle template selection"""
        if index is None:
            return

        templates = self.template_manager.get_all_templates()

        if index < len(templates):
            template = templates[index]

            self.selected_template_index = index
            for i, btn in enumerate(self.template_item_buttons):
                if i == index:
                    btn.configure(fg_color="#2F6FED", text_color="#FFFFFF")
                else:
                    btn.configure(fg_color="transparent", text_color=("#1F2937", "#E6E9EF"))

            # Update details
            self.template_name_label.configure(text=template['name'])
            self.template_desc_label.configure(text=template['description'])

            self.template_cmd_text.configure(state='normal')
            self.template_cmd_text.delete('1.0', tk.END)
            self.template_cmd_text.insert('1.0', template['command'])
            self.template_cmd_text.configure(state='disabled')

            # Enable buttons
            self.template_use_btn.configure(state='normal')

            # Only enable delete for custom templates
            if not template.get('is_preset', False):
                self.template_delete_btn.configure(state='normal')
            else:
                self.template_delete_btn.configure(state='disabled')

    def _use_template(self):
        """Use the selected template for download"""
        if self.selected_template_index is None:
            return

        index = self.selected_template_index
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
                self._set_template_mode(True, template['name'])

                messagebox.showinfo(
                    "Template Ready",
                    f"Template '{template['name']}' is ready.\n\n"
                    f"Download settings are locked while template is active.\n"
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
        if self.selected_template_index is None:
            return

        index = self.selected_template_index
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
                    self.template_cmd_text.configure(state='normal')
                    self.template_cmd_text.delete('1.0', tk.END)
                    self.template_cmd_text.configure(state='disabled')
                    self.template_use_btn.configure(state='disabled')
                    self.template_delete_btn.configure(state='disabled')
                else:
                    messagebox.showerror("Error", "Failed to delete template")
