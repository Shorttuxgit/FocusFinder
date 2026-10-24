import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
import customtkinter as ctk

from src.constants import BG_DARK, BG_SURFACE, BG_CARD, BG_HOVER, FG_TEXT, FG_SUBTEXT, FG_ACCENT
from src.config_manager import load_config, write_to_config

class TimetableWidget:
    def __init__(self, root, events, student_name):
        self.root = root
        self.events = events
        self.student_name = student_name
        
        config = load_config()
        self.sett_enabled = config.get("sett_enabled", False)
        self.time_format = config.get("time_format", False)
        self.update_time_format_variables()

        current_Date = datetime.now()
        current_time = current_Date.strftime("%p")
        self.greeting = "Good Morning," if current_time == "AM" else "Good Afternoon,"

        self.grouped_days = self.process_events(events)
        self.available_dates = sorted(list(self.grouped_days.keys()))

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
        if self.time_format:
            self.formats = "%I"
            self.isPOM = "%p"
            self.isPOMenable = "Enabled" 
        else:
            self.formats = "%H"
            self.isPOM = ""
            self.isPOMenable = "Disabled" 

    def configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Treeview", background=BG_SURFACE, foreground=FG_TEXT, fieldbackground=BG_SURFACE, bordercolor=BG_DARK, rowheight=34, font=("Arial", 13))
        style.map("Treeview", background=[("selected", BG_HOVER)], foreground=[("selected", FG_TEXT)])
        style.configure("Treeview.Heading", background=BG_CARD, foreground=FG_ACCENT, bordercolor=BG_DARK, font=("Arial", 10, "bold"))
        style.configure("Vertical.TScrollbar", gripcount=0, background=BG_CARD, troughcolor=BG_SURFACE, bordercolor=BG_DARK, arrowcolor=FG_TEXT)

    def create_widgets(self):
        self.main_container = ctk.CTkFrame(self.root, fg_color=BG_DARK, corner_radius=0)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        welcome_card = ctk.CTkFrame(self.main_container, fg_color=BG_CARD, corner_radius=16)
        welcome_card.pack(fill=tk.X, pady=(0, 12), ipadx=12, ipady=8)

        welcome_label = ctk.CTkLabel(welcome_card, text=f"{self.greeting} {self.student_name}", font=("Arial", 18, "bold"), text_color=FG_ACCENT)
        welcome_label.pack(side=tk.LEFT, padx=12, pady=6)

        if self.sett_enabled:
            sett_btn = ctk.CTkButton(
                welcome_card, text="Settings", font=("Arial", 12, "bold"),
                fg_color=BG_HOVER, hover_color="#585b70", text_color=FG_TEXT,
                command=self.open_settings, corner_radius=12, height=36, width=90
            )
            sett_btn.pack(side=tk.RIGHT, padx=10)

        nav_card = ctk.CTkFrame(self.main_container, fg_color=BG_CARD, corner_radius=16)
        nav_card.pack(fill=tk.X, pady=(0, 15), ipadx=12, ipady=10)

        self.prev_btn = ctk.CTkButton(nav_card, text="<< Previous Day", command=self.prev_day, font=("Arial", 12, "bold"), fg_color=BG_HOVER, hover_color="#585b70", text_color=FG_TEXT, corner_radius=12, height=36, width=140)
        self.prev_btn.pack(side=tk.LEFT, padx=(10, 0))

        self.date_label = ctk.CTkLabel(nav_card, text="", font=("Arial", 14, "bold"), text_color=FG_TEXT)
        self.date_label.pack(side=tk.LEFT, expand=True)

        self.next_btn = ctk.CTkButton(nav_card, text="Next Day >>", command=self.next_day, font=("Arial", 12, "bold"), fg_color=BG_HOVER, hover_color="#585b70", text_color=FG_TEXT, corner_radius=12, height=36, width=140)
        self.next_btn.pack(side=tk.RIGHT, padx=(0, 10))

        table_card = ctk.CTkFrame(self.main_container, fg_color=BG_SURFACE, corner_radius=16, border_width=1, border_color=BG_HOVER)
        table_card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

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

        bottom_frame = ctk.CTkFrame(self.main_container, fg_color=BG_DARK)
        bottom_frame.pack(fill=tk.X)

        today_btn = ctk.CTkButton(bottom_frame, text="Jump to Today", command=self.jump_to_today, font=("Arial", 12, "bold"), fg_color=FG_ACCENT, hover_color="#b4befe", text_color=BG_DARK, corner_radius=20, height=40, width=160)
        today_btn.pack(side=tk.BOTTOM)

    def process_events(self, events):
        grouped = {}
        for ev in events:
            start_raw = str(ev.get("start", ""))
            end_raw = str(ev.get("end", ""))

            try:
                clean_start = start_raw.split(".")[0].replace("T", " ")
                clean_end = end_raw.split(".")[0].replace("T", " ")

                dt_start = datetime.strptime(clean_start, "%Y-%m-%d %H:%M:%S")
                dt_end = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S")

                if dt_start.weekday() == 5: # Exclude Saturday
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
        if self.current_index > 0:
            self.current_index -= 1
            self.update_display()

    def next_day(self):
        if self.current_index < len(self.available_dates) - 1:
            self.current_index += 1
            self.update_display()

    def jump_to_today(self):
        today_str = date.today().strftime("%Y-%m-%d")
        found = False
        for idx, d_str in enumerate(self.available_dates):
            if d_str == today_str:
                self.current_index = idx
                found = True
                break

        if found:
            self.update_display()
        else:
            messagebox.showinfo("Info", "Time to Relax! No Lessons Today!!")

    def open_settings(self):
        if self.sett_enabled:
            settingwin = ctk.CTkToplevel(self.root)
            settingwin.geometry("400x400")
            settingwin.title("Settings")
            #tracking the switch state
            self.time_var = ctk.IntVar(value=1 if self.time_format else 0)

            self.time_switch = ctk.CTkSwitch(
                settingwin, 
                text="Use 12-Hour Time Format", 
                command=self.toggle_time,
                variable=self.time_var,
                onvalue=1,
                offvalue=0
            )
            self.time_switch.pack(pady=20, padx=20, anchor="w")
            
        else:
            messagebox.showinfo("Settings", "Settings functionality is currently disabled.")

    def toggle_time(self):
        self.time_format = bool(self.time_var.get())  
        self.update_time_format_variables()
        write_to_config("time_format", self.time_format)        
        self.grouped_days = self.process_events(self.events)
        self.update_display()