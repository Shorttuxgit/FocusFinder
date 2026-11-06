import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime, date, timedelta
import customtkinter as ctk

from FocusPY.src.constants import BG_DARK, BG_SURFACE, BG_CARD, BG_HOVER, FG_TEXT, FG_SUBTEXT, FG_ACCENT
from FocusPY.src.config_manager import load_config, write_to_config
from FocusPY.src.friend_manager import export_friend_file, import_friend_file, load_friends, delete_friend

class TimetableWidget:
    def __init__(self, root, events, student_name):
        self.root = root
        self.my_events = events
        self.my_name = student_name

        # Track active view data separately for friend timetable switching
        self.events = events
        self.student_name = student_name
        
        # Load user configuration settings
        config = load_config()
        self.sett_enabled = config.get("sett_enabled", True)
        self.friends_system_enabled = config.get("friends_system", True)
        self.time_format = config.get("time_format", False)
        self.update_time_format_variables()
        # Determine greeting based on current time of day
        current_Date = datetime.now()
        current_time = current_Date.strftime("%p")
        self.greeting = "Good Morning," if current_time == "AM" else "Good Afternoon,"

        # Group timetable events by date
        self.grouped_days = self.process_events(events)
        self.available_dates = sorted(list(self.grouped_days.keys()))

        # Set calendar index to today's date
        self.current_index = 0
        today_str = date.today().strftime("%Y-%m-%d")

        for idx, d_str in enumerate(self.available_dates):
            if d_str == today_str:
                self.current_index = idx
                break
            elif d_str > today_str:
                self.current_index = max(0, idx - 1)
                break

        self.configure_styles()
        self.create_widgets()
        self.update_display()

    def update_time_format_variables(self):
        # Configure time format strings based on user preference
        if self.time_format:
            self.formats = "%I"
            self.isPOM = "%p"
            self.isPOMenable = "Enabled" 
        else:
            self.formats = "%H"
            self.isPOM = ""
            self.isPOMenable = "Disabled" 

    def configure_styles(self):
        # Configure custom table styles for treeview
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Treeview", background=BG_SURFACE, foreground=FG_TEXT, fieldbackground=BG_SURFACE, bordercolor=BG_DARK, rowheight=34, font=("Arial", 13))
        style.map("Treeview", background=[("selected", BG_HOVER)], foreground=[("selected", FG_TEXT)])
        style.configure("Treeview.Heading", background=BG_CARD, foreground=FG_ACCENT, bordercolor=BG_DARK, font=("Arial", 10, "bold"))
        style.configure("Vertical.TScrollbar", gripcount=0, background=BG_CARD, troughcolor=BG_SURFACE, bordercolor=BG_DARK, arrowcolor=FG_TEXT)

    def create_widgets(self):
        # Main application layout container
        self.main_container = ctk.CTkFrame(self.root, fg_color=BG_DARK, corner_radius=0)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Greeting box in its own separate centered card at the top
        greeting_card = ctk.CTkFrame(self.main_container, fg_color=BG_CARD, corner_radius=16)
        greeting_card.pack(fill=tk.X, pady=(0, 12), ipady=8)

        self.welcome_label = ctk.CTkLabel(
            greeting_card, 
            text=f"{self.greeting} {self.student_name}", 
            font=("Arial", 18, "bold"), 
            text_color=FG_ACCENT
        )
        self.welcome_label.pack(anchor="center", pady=6)

        # Day navigation card
        nav_card = ctk.CTkFrame(self.main_container, fg_color=BG_CARD, corner_radius=16)
        nav_card.pack(fill=tk.X, pady=(0, 12), ipadx=12, ipady=10)

        self.prev_btn = ctk.CTkButton(nav_card, text="<< Previous Day", command=self.prev_day, font=("Arial", 12, "bold"), fg_color=BG_HOVER, hover_color="#585b70", text_color=FG_TEXT, corner_radius=12, height=36, width=140)
        self.prev_btn.pack(side=tk.LEFT, padx=(10, 0))

        self.date_label = ctk.CTkLabel(
            nav_card,
            text="",
            font=("Arial", 14, "bold"),
            text_color=FG_TEXT,
            cursor="hand2"
        )
        self.date_label.pack(side=tk.LEFT, expand=True)
        self.date_label.bind("<Button-1>", self.go_to_today)

        self.next_btn = ctk.CTkButton(nav_card, text="Next Day >>", command=self.next_day, font=("Arial", 12, "bold"), fg_color=BG_HOVER, hover_color="#585b70", text_color=FG_TEXT, corner_radius=12, height=36, width=140)
        self.next_btn.pack(side=tk.RIGHT, padx=(0, 10))

        # Timetable events table card
        table_card = ctk.CTkFrame(self.main_container, fg_color=BG_SURFACE, corner_radius=16, border_width=1, border_color=BG_HOVER)
        table_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        columns = ("Time", "Event Title", "Room", "Staff")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings")
        self.tree.heading("Time", text="Time")
        self.tree.heading("Event Title", text="Event Title")
        self.tree.heading("Room", text="Room")
        self.tree.heading("Staff", text="Staff")

        self.tree.column("Time", width=180, anchor=tk.W)
        self.tree.column("Event Title", width=260, anchor=tk.W)
        self.tree.column("Room", width=80, anchor=tk.W)
        self.tree.column("Staff", width=140, anchor=tk.W)

        scrollbar = ttk.Scrollbar(table_card, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0), pady=12)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 12), pady=12)

        # Bottom toolbar frame holding view switcher dropdown and options button side-by-side
        bottom_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        bottom_frame.pack(fill=tk.X, pady=(0, 5))

        bottom_inner = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        bottom_inner.pack(expand=True, anchor="center")

        if self.friends_system_enabled:
            friend_data = load_friends()
            view_options = ["My Timetable"] + [f"Friend: {name}" for name in friend_data.keys()]
            
            self.view_var = tk.StringVar(value=view_options[0])
            self.view_dropdown = ctk.CTkOptionMenu(
                bottom_inner, values=view_options, command=self.switch_timetable_view,
                variable=self.view_var, width=190, height=36, fg_color=BG_HOVER, button_color=BG_DARK
            )
            self.view_dropdown.pack(side=tk.LEFT, padx=6)

        if self.sett_enabled or self.friends_system_enabled:
            options_btn = ctk.CTkButton(
                bottom_inner, text="Options", font=("Arial", 12, "bold"),
                fg_color=BG_HOVER, hover_color="#585b70", text_color=FG_TEXT,
                command=self.open_options_menu, corner_radius=12, height=36, width=110
            )
            options_btn.pack(side=tk.LEFT, padx=6)

    def process_events(self, events):
        # Parse and group events by calendar date, excluding Saturdays
        grouped = {}
        for ev in events:
            start_raw = str(ev.get("start", ""))
            end_raw = str(ev.get("end", ""))

            try:
                clean_start = start_raw.split(".")[0].replace("T", " ")
                clean_end = end_raw.split(".")[0].replace("T", " ")

                dt_start = datetime.strptime(clean_start, "%Y-%m-%d %H:%M:%S")
                dt_end = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S")

                if dt_start.weekday() == 5:
                    continue

                day_key = dt_start.strftime("%Y-%m-%d")
                day_header = dt_start.strftime("%A, %d %B %Y")
                time_str = f"{dt_start.strftime(f'{self.formats}:%M{self.isPOM}')} - {dt_end.strftime(f'{self.formats}:%M{self.isPOM}')}"
            except ValueError:
                dt_start = datetime.min
                day_key = "9999-99-99"
                day_header = "Unscheduled / Other"
                time_str = f"{start_raw} - {end_raw}"

            title = ev.get("title") or "N/A"
            room = str(ev.get("room") or ev.get("extendedProps", {}).get("room") or "—").strip()
            staff = str(ev.get("staff") or ev.get("extendedProps", {}).get("staff") or "—").strip()
            room = room if room else "—"
            staff = staff if staff else "—"

            if day_key not in grouped:
                grouped[day_key] = {"header": day_header, "events": []}

            grouped[day_key]["events"].append({
                "dt_start": dt_start,
                "time": time_str,
                "title": title,
                "room": room,
                "staff": staff
            })

        for day_key in grouped:
            grouped[day_key]["events"].sort(key=lambda x: x["dt_start"])

        return grouped

    def update_display(self):
        # Refresh treeview table rows for the active date
        for row in self.tree.get_children():
            self.tree.delete(row)

        if not self.available_dates:
            self.date_label.configure(text="No Timetable Data Available")
            return

        current_key = self.available_dates[self.current_index]
        day_data = self.grouped_days[current_key]

        self.date_label.configure(text=day_data["header"])

        for e in day_data["events"]:
            self.tree.insert("", tk.END, values=(e["time"], e["title"], e["room"], e["staff"]))

        has_prev = self.current_index > 0
        has_next = self.current_index < len(self.available_dates) - 1

        self.prev_btn.configure(state="normal" if has_prev else "disabled", fg_color=BG_HOVER if has_prev else BG_SURFACE, text_color=FG_TEXT if has_prev else FG_SUBTEXT)
        self.next_btn.configure(state="normal" if has_next else "disabled", fg_color=BG_HOVER if has_next else BG_SURFACE, text_color=FG_TEXT if has_next else FG_SUBTEXT)

    def prev_day(self):
        # Move to the previous day in the timetable view
        if self.current_index > 0:
            self.current_index -= 1
            self.update_display()

    def next_day(self):
        # Move to the next day in the timetable view
        if self.current_index < len(self.available_dates) - 1:
            self.current_index += 1
            self.update_display()

    def go_to_today(self, _event=None):
        # Jump to today's date when it belongs to the displayed timetable week
        today = date.today()
        today_key = today.isoformat()

        if today.weekday() >= 5:
            return

        if today_key not in self.grouped_days:
            if not self.available_dates:
                return

            today_week_start = today - timedelta(days=today.weekday())
            timetable_contains_today_week = any(
                date.fromisoformat(day_key)
                - timedelta(days=date.fromisoformat(day_key).weekday())
                == today_week_start
                for day_key in self.available_dates
            )

            if not timetable_contains_today_week:
                return

            self.grouped_days[today_key] = {
                "header": today.strftime("%A, %d %B %Y"),
                "events": []
            }
            self.available_dates = sorted(self.grouped_days.keys())

        self.current_index = self.available_dates.index(today_key)
        self.update_display()

    def switch_timetable_view(self, choice):
        # Switch active timetable between user schedule and selected friend schedule
        if choice == "My Timetable":
            self.student_name = self.my_name
            self.events = self.my_events
        else:
            friend_name = choice.replace("Friend: ", "").strip()
            friend_data = load_friends()
            if friend_name in friend_data:
                self.student_name = friend_name
                self.events = friend_data[friend_name]
        
        self.grouped_days = self.process_events(self.events)
        self.available_dates = sorted(list(self.grouped_days.keys()))
        self.current_index = 0
        
        self.welcome_label.configure(text=f"{self.greeting} {self.student_name}")
        self.update_display()

    def show_safe_message(self, title, message, is_error=False, parent=None):
        # Display a modal message attached to the window that triggered it
        target = parent or self.root
        box = ctk.CTkToplevel(target)
        box.geometry("340x170")
        box.title(title)
        box.resizable(False, False)
        box.transient(target)

        ctk.CTkLabel(
            box,
            text=message,
            font=("Arial", 12),
            text_color=FG_TEXT,
            wraplength=300
        ).pack(pady=(25, 20), padx=20)

        btn_color = "#f38ba8" if is_error else FG_ACCENT
        ok_btn = ctk.CTkButton(
            box,
            text="OK",
            command=box.destroy,
            fg_color=btn_color,
            text_color=BG_DARK,
            font=("Arial", 12, "bold"),
            height=32,
            width=100
        )
        ok_btn.pack(pady=(0, 15))

        box.wait_visibility()
        box.lift()
        box.focus_force()
        box.grab_set()
        target.wait_window(box)

        if target is not self.root and target.winfo_exists():
            target.grab_set()
            target.lift()
            target.focus_force()

    def show_safe_confirm(self, title, message, parent=None):
        # Display a modal confirmation attached to its parent window
        target = parent or self.root
        box = ctk.CTkToplevel(target)
        box.geometry("340x170")
        box.title(title)
        box.resizable(False, False)
        box.transient(target)

        result = {"confirmed": False}

        ctk.CTkLabel(
            box,
            text=message,
            font=("Arial", 12),
            text_color=FG_TEXT,
            wraplength=300
        ).pack(pady=(25, 20), padx=20)

        btn_frame = ctk.CTkFrame(box, fg_color="transparent")
        btn_frame.pack(pady=(0, 15))

        def on_yes():
            result["confirmed"] = True
            box.destroy()

        yes_btn = ctk.CTkButton(
            btn_frame,
            text="Yes",
            command=on_yes,
            fg_color="#f38ba8",
            text_color=BG_DARK,
            font=("Arial", 12, "bold"),
            height=32,
            width=80
        )
        yes_btn.pack(side=tk.LEFT, padx=10)

        no_btn = ctk.CTkButton(
            btn_frame,
            text="No",
            command=box.destroy,
            fg_color=BG_HOVER,
            text_color=FG_TEXT,
            font=("Arial", 12, "bold"),
            height=32,
            width=80
        )
        no_btn.pack(side=tk.LEFT, padx=10)

        box.wait_visibility()
        box.lift()
        box.focus_force()
        box.grab_set()
        target.wait_window(box)

        if target is not self.root and target.winfo_exists():
            target.grab_set()
            target.lift()
            target.focus_force()

        return result["confirmed"]

    def open_options_menu(self):
        # Open unified options menu window for settings and friend management
        opt_win = ctk.CTkToplevel(self.root)
        opt_win.geometry("380x360")
        opt_win.title("Options")
        opt_win.resizable(False, False)
        
        opt_win.transient(self.root)
        self.options_window = opt_win

        ctk.CTkLabel(opt_win, text="App & Friends Options", font=("Arial", 16, "bold"), text_color=FG_ACCENT).pack(pady=(20, 15))

        if self.sett_enabled:
            self.time_var = ctk.IntVar(value=1 if self.time_format else 0)
            time_switch = ctk.CTkSwitch(
                opt_win, text="Use 12-Hour Time Format", command=self.toggle_time,
                variable=self.time_var, onvalue=1, offvalue=0
            )
            time_switch.pack(pady=8, padx=25, anchor="w")

        if self.friends_system_enabled:
            share_btn = ctk.CTkButton(
                opt_win, text="Export My Timetable", font=("Arial", 12, "bold"),
                fg_color=BG_HOVER, hover_color="#585b70", text_color=FG_TEXT,
                command=lambda: self.export_my_timetable_file(parent=opt_win), height=36, width=310
            )
            share_btn.pack(pady=8)

            add_btn = ctk.CTkButton(
                opt_win, text="Import Friend Timetable", font=("Arial", 12, "bold"),
                fg_color=BG_HOVER, hover_color="#585b70", text_color=FG_TEXT,
                command=self.open_add_friend_dialog, height=36, width=310
            )
            add_btn.pack(pady=8)

            friend_data = load_friends()
            if friend_data:
                delete_frame = ctk.CTkFrame(opt_win, fg_color="transparent")
                delete_frame.pack(pady=10)

                friend_names = list(friend_data.keys())
                del_var = tk.StringVar(value=friend_names[0])
                del_dropdown = ctk.CTkOptionMenu(delete_frame, values=friend_names, variable=del_var, width=180)
                del_dropdown.pack(side=tk.LEFT, padx=5)

                def remove_friend():
                    selected_friend = del_var.get()
                    if self.show_safe_confirm("Confirm", f"Remove {selected_friend} from friends?", parent=opt_win):
                        delete_friend(selected_friend)
                        self.show_safe_message("Success", f"Removed {selected_friend}.", parent=opt_win)
                        opt_win.destroy()
                        self.options_window = None
                        self.refresh_dropdown_options()

                del_btn = ctk.CTkButton(
                    delete_frame, text="Delete Friend", fg_color="#f38ba8", hover_color="#eba0ac",
                    text_color=BG_DARK, font=("Arial", 11, "bold"), command=remove_friend, width=110, height=28
                )
                del_btn.pack(side=tk.LEFT, padx=5)

        opt_win.wait_visibility()
        opt_win.lift()
        opt_win.focus_force()
        opt_win.grab_set()
        opt_win.protocol("WM_DELETE_WINDOW", lambda: self.close_options_menu(opt_win))

    def close_options_menu(self, window):
        if window.winfo_exists():
            window.grab_release()
            window.destroy()
        if getattr(self, "options_window", None) is window:
            self.options_window = None

    def toggle_time(self):
        # Toggle 12-hour or 24-hour time format preference and refresh display
        self.time_format = bool(self.time_var.get())  
        self.update_time_format_variables()
        write_to_config("time_format", self.time_format)        
        self.grouped_days = self.process_events(self.events)
        self.update_display()

    def export_my_timetable_file(self, parent=None):
        # Export the current user's timetable as an Android-compatible file
        dialog_parent = parent or getattr(self, "options_window", None) or self.root
        try:
            output_file = export_friend_file(self.my_name, self.my_events)
            self.show_safe_message(
                "Timetable Exported",
                f"Your Android-compatible timetable has been saved to:\n\n{output_file}",
                parent=dialog_parent
            )
        except Exception as e:
            self.show_safe_message(
                "Export Error",
                f"Could not save your timetable: {e}",
                is_error=True,
                parent=dialog_parent
            )

    def open_add_friend_dialog(self):
        # Open a file picker to import an Android-compatible friend timetable
        dialog_parent = getattr(self, "options_window", None) or self.root
        file_path = filedialog.askopenfilename(
            parent=dialog_parent,
            title="Import Friend Timetable",
            filetypes=[
                ("FocusFinder timetable files", "*.fff"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        try:
            name, _events = import_friend_file(file_path)
            self.refresh_dropdown_options()
            self.show_safe_message(
                "Friend Imported",
                f"Successfully imported {name}'s timetable.",
                parent=dialog_parent
            )
        except Exception as e:
            self.show_safe_message(
                "Import Error",
                f"Could not import this timetable file: {e}",
                is_error=True,
                parent=dialog_parent
            )

    def refresh_dropdown_options(self):
        # Refresh view dropdown values when friends are added or removed
        if not self.friends_system_enabled:
            return
        friend_data = load_friends()
        view_options = ["My Timetable"] + [f"Friend: {name}" for name in friend_data.keys()]
        self.view_dropdown.configure(values=view_options)
        if self.view_var.get() not in view_options:
            self.view_var.set("My Timetable")
            self.switch_timetable_view("My Timetable")