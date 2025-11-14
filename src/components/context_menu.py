"""Context menu utility for text widgets"""

import tkinter as tk


class ContextMenu:
    """Provides right-click context menu for text input widgets"""

    def __init__(self, widget, read_only=False, on_paste_callback=None):
        """
        Initialize context menu for a widget

        Args:
            widget: The tkinter widget (Entry or Text) to attach context menu to
            read_only: If True, only show copy and select all options
            on_paste_callback: Optional callback function to call after paste operation
        """
        self.widget = widget
        self.read_only = read_only
        self.on_paste_callback = on_paste_callback
        self.menu = tk.Menu(widget, tearoff=0)
        
        # Build menu items
        if not read_only:
            self.menu.add_command(label="Cut", command=self._cut)
            self.menu.add_command(label="Copy", command=self._copy)
            self.menu.add_command(label="Paste", command=self._paste)
            self.menu.add_separator()
            self.menu.add_command(label="Select All", command=self._select_all)
            self.menu.add_command(label="Clear", command=self._clear)
        else:
            # Read-only mode: only copy and select all
            self.menu.add_command(label="Copy", command=self._copy)
            self.menu.add_separator()
            self.menu.add_command(label="Select All", command=self._select_all)
        
        # Bind right-click to show menu
        self.widget.bind("<Button-3>", self._show_menu)
        # Also bind Shift+F10 for accessibility
        self.widget.bind("<Shift-F10>", self._show_menu)
    
    def _show_menu(self, event):
        """Show context menu at cursor position"""
        try:
            # Update menu item states based on current context
            self._update_menu_states()
            self.menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError:
            pass
        finally:
            self.menu.grab_release()

    def _update_menu_states(self):
        """Update menu item states based on widget content and selection"""
        # Check if there's text in the widget
        has_text = False
        has_selection = False

        try:
            if isinstance(self.widget, tk.Entry):
                has_text = len(self.widget.get()) > 0
                # For Entry widget, check if there's a selection
                try:
                    selection = self.widget.selection_get()
                    has_selection = len(selection) > 0
                except tk.TclError:
                    # No selection
                    has_selection = False
            else:  # Text widget
                has_text = len(self.widget.get("1.0", tk.END).strip()) > 0
                has_selection = len(self.widget.tag_ranges(tk.SEL)) > 0
        except tk.TclError:
            pass

        # Check clipboard
        has_clipboard = False
        try:
            # Get the root window to access clipboard
            root = self.widget.winfo_toplevel()
            clipboard_text = root.clipboard_get()
            has_clipboard = len(clipboard_text.strip()) > 0
        except tk.TclError:
            pass

        # Update menu items
        menu_items = self.menu.index("end")
        if menu_items is not None:
            for i in range(menu_items + 1):
                try:
                    item_label = self.menu.entryconfig(i, "label")[4][4]

                    if item_label == "Cut":
                        state = "normal" if has_selection else "disabled"
                        self.menu.entryconfig(i, state=state)
                    elif item_label == "Copy":
                        state = "normal" if has_selection else "disabled"
                        self.menu.entryconfig(i, state=state)
                    elif item_label == "Paste":
                        state = "normal" if has_clipboard and not self.read_only else "disabled"
                        self.menu.entryconfig(i, state=state)
                    elif item_label == "Select All":
                        state = "normal" if has_text else "disabled"
                        self.menu.entryconfig(i, state=state)
                    elif item_label == "Clear":
                        state = "normal" if has_text else "disabled"
                        self.menu.entryconfig(i, state=state)
                except (tk.TclError, IndexError):
                    pass
    
    def _cut(self):
        """Cut selected text"""
        try:
            if isinstance(self.widget, tk.Entry):
                self.widget.event_generate("<<Cut>>")
            else:  # Text widget
                if self.widget.tag_ranges(tk.SEL):
                    self.widget.event_generate("<<Cut>>")
        except tk.TclError:
            pass
    
    def _copy(self):
        """Copy selected text"""
        try:
            if isinstance(self.widget, tk.Entry):
                self.widget.event_generate("<<Copy>>")
            else:  # Text widget
                if self.widget.tag_ranges(tk.SEL):
                    self.widget.event_generate("<<Copy>>")
        except tk.TclError:
            pass
    
    def _paste(self):
        """Paste from clipboard"""
        try:
            if isinstance(self.widget, tk.Entry):
                self.widget.event_generate("<<Paste>>")
            else:  # Text widget
                self.widget.event_generate("<<Paste>>")

            # Call the paste callback if provided
            if self.on_paste_callback:
                self.widget.after(10, self.on_paste_callback)
        except tk.TclError:
            pass
    
    def _select_all(self):
        """Select all text"""
        try:
            if isinstance(self.widget, tk.Entry):
                self.widget.select_range(0, tk.END)
                self.widget.icursor(tk.END)
            else:  # Text widget
                self.widget.tag_add(tk.SEL, "1.0", tk.END)
                self.widget.mark_set(tk.INSERT, tk.END)
                self.widget.see(tk.INSERT)
        except tk.TclError:
            pass
    
    def _clear(self):
        """Clear all text"""
        try:
            if isinstance(self.widget, tk.Entry):
                self.widget.delete(0, tk.END)
            else:  # Text widget
                self.widget.delete("1.0", tk.END)
        except tk.TclError:
            pass

