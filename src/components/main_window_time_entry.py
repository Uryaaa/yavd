"""TimeEntry widget for main window."""

import tkinter as tk
import customtkinter as ctk


class TimeEntry(ctk.CTkFrame):
    """Custom time entry widget (HH:MM:SS) with up/down arrow support and backspace/del reset to 0."""

    def __init__(self, master, width=120, state='normal', **kwargs):
        super().__init__(master, fg_color="transparent")
        self._time_var = tk.StringVar(value="00:00:00")
        self._state = state
        self._entry = ctk.CTkEntry(self, width=width, font=('Arial', 12),
                                   textvariable=self._time_var, justify='center')
        self._entry.pack(fill=tk.X)

        # Bind events on the internal tk entry for reliable key handling
        internal = self._entry._entry
        internal.bind("<KeyPress>", self._on_key_press)
        internal.bind("<Up>", self._on_arrow_up)
        internal.bind("<Down>", self._on_arrow_down)

        if state == 'disabled':
            self._entry.configure(state='disabled')

    def _get_cursor_segment(self):
        """Return which segment (0=hours, 1=minutes, 2=seconds) the cursor is in."""
        try:
            pos = self._entry._entry.index(tk.INSERT)
        except Exception:
            pos = 0
        if pos <= 2:
            return 0
        elif pos <= 5:
            return 1
        else:
            return 2

    def _parse_time(self):
        """Parse current value into [h, m, s]."""
        val = self._time_var.get()
        try:
            parts = val.split(':')
            return [int(parts[0]), int(parts[1]), int(parts[2])]
        except Exception:
            return [0, 0, 0]

    def _format_time(self, h, m, s):
        """Format h, m, s into HH:MM:SS string."""
        h = max(0, min(h, 99))
        m = max(0, min(m, 59))
        s = max(0, min(s, 59))
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _set_time(self, h, m, s):
        """Set the time value and restore cursor position."""
        try:
            pos = self._entry._entry.index(tk.INSERT)
        except Exception:
            pos = 0
        self._time_var.set(self._format_time(h, m, s))
        try:
            self._entry._entry.icursor(pos)
        except Exception:
            pass

    def _on_key_press(self, event):
        """Handle key presses: digits replace at cursor, backspace/del reset to 0."""
        if self._state == 'disabled':
            return "break"

        # Allow navigation keys
        if event.keysym in ('Left', 'Right', 'Home', 'End', 'Tab', 'Shift_L', 'Shift_R'):
            return None

        # Up/Down handled separately
        if event.keysym in ('Up', 'Down'):
            return None

        val = self._time_var.get()
        try:
            pos = self._entry._entry.index(tk.INSERT)
        except Exception:
            pos = 0

        if event.keysym in ('BackSpace', 'Delete'):
            # Reset digit at cursor position to 0
            if event.keysym == 'BackSpace' and pos > 0:
                target = pos - 1
            else:
                target = pos
            # Skip colons
            if target < len(val) and val[target] == ':':
                return "break"
            if 0 <= target < len(val) and val[target] != ':':
                new_val = val[:target] + '0' + val[target + 1:]
                self._time_var.set(new_val)
                self._entry._entry.icursor(target if event.keysym == 'BackSpace' else target + 1)
            return "break"

        if event.char and event.char.isdigit():
            # Skip colon positions
            if pos < len(val) and val[pos] == ':':
                pos += 1
            if pos < len(val) and val[pos] != ':':
                new_val = val[:pos] + event.char + val[pos + 1:]
                # Validate segments
                try:
                    parts = new_val.split(':')
                    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
                    if m > 59 or s > 59 or h > 99:
                        return "break"
                except Exception:
                    return "break"
                self._time_var.set(new_val)
                # Move cursor forward, skip colons
                new_pos = pos + 1
                if new_pos < len(new_val) and new_val[new_pos] == ':':
                    new_pos += 1
                self._entry._entry.icursor(new_pos)
            return "break"

        # Block all other input
        return "break"

    def _on_arrow_up(self, event):
        """Increment the segment at cursor by 1."""
        if self._state == 'disabled':
            return "break"
        seg = self._get_cursor_segment()
        h, m, s = self._parse_time()
        if seg == 0:
            h = min(h + 1, 99)
        elif seg == 1:
            m = min(m + 1, 59)
        else:
            s = min(s + 1, 59)
        self._set_time(h, m, s)
        return "break"

    def _on_arrow_down(self, event):
        """Decrement the segment at cursor by 1."""
        if self._state == 'disabled':
            return "break"
        seg = self._get_cursor_segment()
        h, m, s = self._parse_time()
        if seg == 0:
            h = max(h - 1, 0)
        elif seg == 1:
            m = max(m - 1, 0)
        else:
            s = max(s - 1, 0)
        self._set_time(h, m, s)
        return "break"

    def get(self):
        """Get the current time string."""
        return self._time_var.get().strip()

    def delete(self, start, end):
        """Reset to 00:00:00."""
        self._time_var.set("00:00:00")

    def insert(self, index, value):
        """Set the time value (expects HH:MM:SS format)."""
        # Validate and set
        try:
            parts = value.strip().split(':')
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
            self._time_var.set(self._format_time(h, m, s))
        except Exception:
            self._time_var.set(value)

    def configure(self, **kwargs):
        """Configure the widget."""
        if 'state' in kwargs:
            self._state = kwargs['state']
            self._entry.configure(state=kwargs['state'])
            del kwargs['state']
        if kwargs:
            super().configure(**kwargs)

    def select_range(self, start, end):
        """Select a range of text."""
        self._entry.select_range(start, end)
