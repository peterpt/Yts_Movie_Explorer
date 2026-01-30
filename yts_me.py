import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import threading
import webbrowser
import urllib.parse
import io
import json
import configparser
import sys
import requests
from api_handler import APIHandler
import resources

# --- Visual Constants (Dark Mode) ---
COLOR_BG_DARK = "#2b2b2b"
COLOR_BG_LIGHT = "#3c3f41"
COLOR_ACCENT = "#6ac045"
COLOR_TEXT = "#ffffff"
COLOR_TEXT_DIM = "#aaaaaa"
COLOR_LIST_BG = "#333333"
FONT_MAIN = ('Segoe UI', 10)
FONT_BOLD = ('Segoe UI', 10, 'bold')
FONT_TITLE = ('Segoe UI', 14, 'bold')
FONT_HEADER = ('Segoe UI', 12, 'bold')

BASE_GEOMETRY = "1100x700"
YTS_DOMAINS_FILE = "yts_domains.json"
APP_CONFIG_FILE = "config.ini"
ADDITIONAL_TRACKERS_URL = "https://raw.githubusercontent.com/ngosang/trackerslist/refs/heads/master/trackers_best.txt"

DEFAULT_TRACKERS = [
    "udp://open.demonii.com:1337/announce", "udp://tracker.openbittrent.com:80",
    "udp://tracker.coppersfer.tk:6969", "udp://glotorrents.pw:6969/announce",
    "udp://tracker.opentrackr.org:1337/announce", "udp://p4p.arenabg.com:1337",
]

# --- API Filter Options ---
GENRES = ['All', 'Action', 'Adventure', 'Animation', 'Biography', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Family', 'Fantasy', 'Film-Noir', 'History', 'Horror', 'Music', 'Musical', 'Mystery', 'Romance', 'Sci-Fi', 'Sport', 'Thriller', 'War', 'Western']
QUALITIES = ['All', '480p', '720p', '1080p', '1080p.x265', '2160p', '3D']
RATINGS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
SORT_BY = ['date_added', 'like_count', 'download_count', 'peers', 'seeds', 'rating', 'year', 'title']

# --- Helper: Tooltip Class (Fixed Indentation) ---
class ToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.waittime = 500
        self.wraplength = 180
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None

    def showtip(self):
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#ffffff", relief='solid', borderwidth=1,
                       wraplength=self.wraplength, font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()

# --- Editor Windows ---
class ApiKeyEditorWindow(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.title("Set API Keys")
        self.geometry("450x180")
        self.transient(parent)
        self.grab_set()
        self.callback = callback
        self.configure(bg=COLOR_BG_DARK)
        
        ttk.Label(self, text="Enter your TMDB API Key (v3 Auth) below:", wraplength=430, background=COLOR_BG_DARK, foreground=COLOR_TEXT).pack(padx=10, pady=10)
        
        self.api_key_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.api_key_var, width=60).pack(padx=10, pady=5)
        
        button_frame = ttk.Frame(self, padding=10, style="Dark.TFrame")
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Save", command=self._on_save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        self._load_key()

    def _load_key(self):
        try:
            config = configparser.ConfigParser()
            config.read(APP_CONFIG_FILE)
            self.api_key_var.set(config.get('TMDB', 'api_key', fallback=""))
        except Exception:
            pass

    def _on_save(self):
        try:
            config = configparser.ConfigParser()
            config.read(APP_CONFIG_FILE)
            if not config.has_section('TMDB'):
                config.add_section('TMDB')
            config.set('TMDB', 'api_key', self.api_key_var.get())
            with open(APP_CONFIG_FILE, 'w') as f:
                config.write(f)
            self.callback()
            self.destroy()
        except Exception:
            pass

class DomainEditorWindow(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.title("Edit YTS Domains")
        self.geometry("400x500")
        self.transient(parent)
        self.grab_set()
        self.callback = callback
        self.configure(bg=COLOR_BG_DARK)
        
        ttk.Label(self, text="Edit YTS domains (one per line):", background=COLOR_BG_DARK, foreground=COLOR_TEXT).pack(padx=10, pady=10)
        
        text_frame = ttk.Frame(self)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.text_editor = tk.Text(text_frame, wrap="word", bg=COLOR_LIST_BG, fg=COLOR_TEXT, insertbackground='white', font=('Consolas', 10))
        self.scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_editor.yview)
        self.text_editor.config(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        button_frame = ttk.Frame(self, padding=10, style="Dark.TFrame")
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Save", command=self._on_save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        self._load_domains()

    def _load_domains(self):
        try:
            with open(YTS_DOMAINS_FILE, 'r') as f:
                self.text_editor.insert(tk.END, "\n".join(json.load(f)))
        except Exception:
            pass

    def _on_save(self):
        raw_text = self.text_editor.get("1.0", tk.END)
        domains = [line.strip() for line in raw_text.split("\n") if line.strip()]
        try:
            with open(YTS_DOMAINS_FILE, 'w') as f:
                json.dump(domains, f, indent=4)
            self.callback()
            self.destroy()
        except Exception:
            pass

# --- Main Application Class ---
class MovieApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YTS Movie Explorer")
        self.root.geometry(BASE_GEOMETRY)
        self.root.minsize(900, 600)
        self.root.configure(bg=COLOR_BG_DARK)
        
        try:
            self.root.iconphoto(True, resources.get_app_icon())
        except:
            pass

        self.api = APIHandler()
        self.movies_cache = []
        self.current_movie_details = None
        self.current_page = 1
        self.total_movie_count = 0
        self.last_selected_movie_id = None
        self._resize_job = None
        self.last_sort = {'col': None, 'rev': False}
        self.current_poster_data = None
        
        self.all_trackers = list(DEFAULT_TRACKERS)
        threading.Thread(target=self._fetch_additional_trackers, daemon=True).start()

        self._setup_dark_theme()
        self._setup_ui()
        self._on_search()
        self.details_frame.bind('<Configure>', self._on_panel_resize)

    def _fetch_additional_trackers(self):
        try:
            response = requests.get(ADDITIONAL_TRACKERS_URL, timeout=10)
            if response.status_code == 200:
                new_trackers = [line.strip() for line in response.text.split('\n') if line.strip()]
                combined = set(self.all_trackers)
                combined.update(new_trackers)
                self.all_trackers = list(combined)
        except:
            pass

    def _setup_dark_theme(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background=COLOR_BG_DARK)
        style.configure("Dark.TFrame", background=COLOR_BG_DARK)
        style.configure("Card.TFrame", background=COLOR_BG_LIGHT, relief="flat")
        style.configure("TLabel", background=COLOR_BG_DARK, foreground=COLOR_TEXT, font=FONT_MAIN)
        style.configure("Card.TLabel", background=COLOR_BG_LIGHT, foreground=COLOR_TEXT, font=FONT_MAIN)
        style.configure("Header.TLabel", font=FONT_HEADER, foreground=COLOR_ACCENT)
        style.configure("Title.TLabel", font=FONT_TITLE, foreground=COLOR_TEXT)
        style.configure("Sub.TLabel", font=FONT_MAIN, foreground=COLOR_TEXT_DIM)
        style.configure("TButton", background=COLOR_BG_LIGHT, foreground=COLOR_TEXT, borderwidth=0, font=FONT_MAIN, focuscolor=COLOR_ACCENT)
        style.map("TButton", background=[('active', COLOR_ACCENT), ('disabled', '#555555')])
        style.configure("Accent.TButton", background=COLOR_ACCENT, foreground="white", font=FONT_BOLD)
        style.map("Accent.TButton", background=[('active', '#5ab035')])
        style.configure("Trailer.TButton", background="#cc0000", foreground="white", font=FONT_BOLD)
        style.map("Trailer.TButton", background=[('active', '#ff3333')])
        style.configure("TEntry", fieldbackground="#444444", foreground=COLOR_TEXT, insertcolor="white", borderwidth=0)
        style.configure("TCombobox", fieldbackground="#444444", background=COLOR_BG_LIGHT, foreground=COLOR_TEXT, arrowcolor="white")
        style.map("TCombobox", fieldbackground=[('readonly', '#444444')])
        style.configure("TCheckbutton", background=COLOR_BG_DARK, foreground=COLOR_TEXT)
        style.map("TCheckbutton", background=[('active', COLOR_BG_DARK)])
        style.configure("Treeview", background=COLOR_LIST_BG, foreground=COLOR_TEXT, fieldbackground=COLOR_LIST_BG, borderwidth=0, font=('Segoe UI', 10))
        style.configure("Treeview.Heading", background=COLOR_BG_LIGHT, foreground=COLOR_TEXT, font=FONT_BOLD, relief="flat")
        style.map("Treeview.Heading", background=[('active', '#444444')])
        style.map("Treeview", background=[('selected', COLOR_ACCENT)], foreground=[('selected', 'white')])
        style.configure("TNotebook", background=COLOR_BG_DARK, borderwidth=0)
        style.configure("TNotebook.Tab", background=COLOR_BG_LIGHT, foreground=COLOR_TEXT, padding=[10, 5], font=FONT_BOLD, borderwidth=0)
        style.map("TNotebook.Tab", background=[('selected', COLOR_ACCENT)], foreground=[('selected', 'white')])

    def _setup_ui(self):
        self.main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        self.filter_frame = self._create_filter_panel(self.main_pane)
        self.main_pane.add(self.filter_frame, weight=1)
        
        self.center_panel = self._create_center_panel(self.main_pane)
        self.main_pane.add(self.center_panel, weight=3)
        
        self.details_frame = self._create_details_panel(self.main_pane)
        self.main_pane.add(self.details_frame, weight=3) 

    def _create_filter_panel(self, parent):
        frame = ttk.Frame(parent, padding=15, style="Dark.TFrame")
        ttk.Label(frame, text="FILTERS", style="Header.TLabel").pack(fill=tk.X, pady=(0, 15))
        
        def add_filter(label, var, values=None, is_combo=True):
            ttk.Label(frame, text=label, style="Sub.TLabel").pack(fill=tk.X, pady=(10, 2))
            if is_combo:
                cb = ttk.Combobox(frame, textvariable=var, values=values, state='readonly')
                cb.pack(fill=tk.X)
                return cb
            else:
                ent = ttk.Entry(frame, textvariable=var)
                ent.pack(fill=tk.X, ipady=3)
                return ent

        self.search_term = tk.StringVar()
        s_ent = add_filter("Search:", self.search_term, is_combo=False)
        s_ent.bind("<Return>", lambda e: self._on_search())
        
        self.genre = tk.StringVar(value='All')
        add_filter("Genre:", self.genre, GENRES)
        
        self.quality = tk.StringVar(value='All')
        add_filter("Quality:", self.quality, QUALITIES)
        
        self.rating = tk.IntVar(value=0)
        add_filter("Min Rating:", self.rating, RATINGS)
        
        self.sort_by = tk.StringVar(value='date_added')
        add_filter("Sort By:", self.sort_by, SORT_BY)
        
        self.order_by = tk.StringVar(value='desc')
        ttk.Checkbutton(frame, text="Ascending Order", variable=self.order_by, onvalue='asc', offvalue='desc', style="TCheckbutton").pack(fill=tk.X, pady=10)
        
        try:
            search_icon = resources.get_icon("search", 16, 16)
        except:
            search_icon = None
            
        btn = ttk.Button(frame, text=" FIND MOVIES", command=self._on_search, style="Accent.TButton", image=search_icon, compound=tk.LEFT)
        btn.pack(fill=tk.X, pady=(20, 10), ipady=5)
        
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=15)
        ttk.Button(frame, text="⚙ Settings / API", command=self._open_api_key_editor).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="🌐 Domains", command=self._open_domain_editor).pack(fill=tk.X, pady=2)
        return frame

    def _create_center_panel(self, parent):
        frame = ttk.Frame(parent, padding=0, style="Dark.TFrame")
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("title", "year", "rating", "genre")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode="browse")
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.heading("title", text="Title", command=lambda: self._sort_column("title"))
        self.tree.heading("year", text="Year", command=lambda: self._sort_column("year"))
        self.tree.heading("rating", text="★", command=lambda: self._sort_column("rating"))
        self.tree.heading("genre", text="Genre", command=lambda: self._sort_column("genre"))
        
        self.tree.column("title", width=250, minwidth=150)
        self.tree.column("year", width=60, anchor='center')
        self.tree.column("rating", width=40, anchor='center')
        self.tree.column("genre", width=100)
        
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_movie_select)
        
        self.status_label = ttk.Label(tree_frame, text="Loading...", font=('Segoe UI', 14), background=COLOR_LIST_BG, foreground="white", anchor='center')
        
        nav_frame = ttk.Frame(frame, padding=5, style="Dark.TFrame")
        nav_frame.pack(fill=tk.X)
        
        try:
            prev_icon = resources.get_icon("prev", 16, 16)
            next_icon = resources.get_icon("next", 16, 16)
        except:
            prev_icon=None
            next_icon=None
            
        self.btn_prev = ttk.Button(nav_frame, text=" Prev", command=self._prev_page, state=tk.DISABLED, image=prev_icon, compound=tk.LEFT)
        self.btn_prev.pack(side=tk.LEFT)
        
        self.page_label = ttk.Label(nav_frame, text="Page 1", anchor='center')
        self.page_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.btn_next = ttk.Button(nav_frame, text="Next ", command=self._next_page, state=tk.DISABLED, image=next_icon, compound=tk.RIGHT)
        self.btn_next.pack(side=tk.RIGHT)
        
        return frame

    def _create_details_panel(self, parent):
        main_frame = ttk.Frame(parent, padding=10, style="Dark.TFrame")
        
        self.poster_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        self.poster_frame.pack(fill=tk.X, pady=(0, 10))
        
        try:
            placeholder = resources.get_icon("placeholder", 64, 64)
        except:
            placeholder = None
            
        self.poster_label = ttk.Label(self.poster_frame, image=placeholder, background="#222222", anchor="center")
        self.poster_label.pack(pady=0, anchor="center")
        self.poster_label.image = placeholder
        
        self.info_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        self.info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_title = ttk.Label(self.info_frame, text="Select a Movie", style="Title.TLabel", justify="center", anchor="center", wraplength=400)
        self.lbl_title.pack(fill=tk.X)
        
        self.lbl_meta = ttk.Label(self.info_frame, text="", style="Sub.TLabel", justify="center", anchor="center")
        self.lbl_meta.pack(fill=tk.X)
        
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self.tab_story = ttk.Frame(self.notebook, style="Card.TFrame", padding=10)
        self.notebook.add(self.tab_story, text='  Story & Cast  ')
        
        self.story_text = tk.Text(self.tab_story, wrap="word", height=8, bg=COLOR_BG_LIGHT, fg=COLOR_TEXT, bd=0, font=('Segoe UI', 10), selectbackground=COLOR_ACCENT)
        story_scroll = ttk.Scrollbar(self.tab_story, orient="vertical", command=self.story_text.yview)
        
        self.story_text.configure(yscrollcommand=story_scroll.set)
        story_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.story_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.story_text.insert(tk.END, "Select a movie to see the synopsis here...")
        self.story_text.config(state="disabled")
        
        ttk.Separator(self.tab_story, orient='horizontal').pack(fill='x', pady=10)
        
        self.trailer_btn = ttk.Button(self.tab_story, text="▶ Watch Trailer", style="Trailer.TButton", state="disabled")
        self.trailer_btn.pack(fill=tk.X, pady=(0, 5))
        
        self.lbl_cast = ttk.Label(self.tab_story, text="Cast: N/A", style="Card.TLabel", wraplength=350)
        self.lbl_cast.pack(fill=tk.X, anchor="w")
        
        self.tab_down = ttk.Frame(self.notebook, style="Card.TFrame", padding=10)
        self.notebook.add(self.tab_down, text='  Downloads  ')
        
        ttk.Label(self.tab_down, text="Available Torrents:", style="Header.TLabel", background=COLOR_BG_LIGHT).pack(anchor="w", pady=(0,10))
        
        canvas = tk.Canvas(self.tab_down, bg=COLOR_BG_LIGHT, highlightthickness=0)
        sb = ttk.Scrollbar(self.tab_down, orient="vertical", command=canvas.yview)
        self.dl_scroll_frame = ttk.Frame(canvas, style="Card.TFrame")
        
        self.dl_scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.dl_scroll_frame, anchor="nw")
        
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.tab_specs = ttk.Frame(self.notebook, style="Card.TFrame", padding=10)
        self.notebook.add(self.tab_specs, text='  Specs  ')
        
        self.lbl_specs = ttk.Label(self.tab_specs, text="No data selected.", style="Card.TLabel", justify="left")
        self.lbl_specs.pack(fill=tk.BOTH, expand=True, anchor="nw")
        
        return main_frame

    # --- Event Handlers ---
    def _open_domain_editor(self):
        DomainEditorWindow(self.root, callback=self._on_domains_updated)

    def _open_api_key_editor(self):
        ApiKeyEditorWindow(self.root, callback=self._on_api_key_updated)

    def _on_domains_updated(self):
        self.api.reload_yts_domains()
        messagebox.showinfo("Updated", "Domains updated.")

    def _on_api_key_updated(self):
        self.api.reload_app_config()

    def _sort_column(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        
        def get_sort_key(item):
            value = item[0]
            if col in ['year', 'rating']:
                try:
                    return float(value)
                except:
                    return 0.0
            return value.lower()
            
        reverse = self.last_sort['col'] == col and not self.last_sort['rev']
        self.last_sort = {'col': col, 'rev': reverse}
        items.sort(key=get_sort_key, reverse=reverse)
        
        for index, (val, k) in enumerate(items):
            self.tree.move(k, '', index)

    def _on_panel_resize(self, event):
        self.lbl_title.config(wraplength=event.width - 20)
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(300, self._resize_poster_job)

    def _resize_poster_job(self):
        if self.current_poster_data:
            self._apply_poster_image(self.current_poster_data)
    
    def _on_search(self, page=1):
        self.current_page = page
        self.last_selected_movie_id = None
        self._set_ui_state(tk.DISABLED)
        self.tree.delete(*self.tree.get_children())
        
        self.status_label.config(text="Searching YTS...", background=COLOR_LIST_BG)
        self.status_label.place(relx=0.5, rely=0.5, anchor='center', relwidth=1.0, relheight=1.0)
        self.status_label.lift()
        
        threading.Thread(target=self._perform_search, daemon=True).start()
    
    def _perform_search(self):
        try:
            params = {'page': self.current_page, 'sort_by': self.sort_by.get(), 'order_by': self.order_by.get()}
            if self.search_term.get():
                params['query_term'] = self.search_term.get()
            if self.genre.get() != 'All':
                params['genre'] = self.genre.get()
            if self.quality.get() != 'All':
                params['quality'] = self.quality.get()
            if self.rating.get() > 0:
                params['minimum_rating'] = self.rating.get()
            
            data = self.api.list_movies(**params)
            self.total_movie_count = data.get('movie_count', 0)
            self.root.after(0, self._update_results_list, data.get('movies', []))
        except Exception as e:
            self.root.after(0, self._show_error, str(e))
        finally:
            self.root.after(0, self._set_ui_state, tk.NORMAL)

    def _update_results_list(self, movies):
        self.tree.delete(*self.tree.get_children())
        self.movies_cache = movies
        
        if not movies:
            self._clear_all_details()
            self.status_label.config(text="No movies found.")
            self.status_label.lift()
        else:
            self.status_label.place_forget()
            for movie in movies:
                genres = ', '.join(movie.get('genres', ['N/A'])[:2])
                self.tree.insert("", tk.END, iid=movie['id'], values=(
                    movie.get('title', 'Unknown'),
                    movie.get('year', 'N/A'),
                    movie.get('rating', 0),
                    genres
                ))
            if self.tree.get_children():
                first = self.tree.get_children()[0]
                self.tree.selection_set(first)
                self.tree.focus(first)
        self._update_pagination()
    
    def _on_movie_select(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        movie_id = int(selection[0])
        if movie_id == self.last_selected_movie_id:
            return
        
        self.last_selected_movie_id = movie_id
        self._clear_all_details()
        self.lbl_title.config(text="Loading Details...")
        
        # --- CACHE LOGIC ---
        cached_movie = next((m for m in self.movies_cache if m['id'] == movie_id), None)
        threading.Thread(target=self._load_movie_details, args=(movie_id, cached_movie), daemon=True).start()
    
    def _load_movie_details(self, movie_id, cached_movie):
        try:
            yts = self.api.get_movie_details(movie_id)
            if not yts:
                if cached_movie:
                    movie = cached_movie
                else:
                    return
            else:
                movie = yts['movie']

            if self.last_selected_movie_id != movie['id']:
                return
            
            # TMDB Enhance
            imdb = movie.get('imdb_code')
            tmdb_extras = self.api.get_tmdb_details(imdb)
            if tmdb_extras:
                movie.update(tmdb_extras)
            
            # --- FALLBACK DESCRIPTION LOGIC ---
            if cached_movie:
                if not movie.get('description_full') and not movie.get('description_intro'):
                    if cached_movie.get('summary'):
                        movie['description_full'] = cached_movie['summary']
                    elif cached_movie.get('synopsis'):
                        movie['description_full'] = cached_movie['synopsis']

            self.current_movie_details = movie
            self.root.after(0, self._populate_all_details, movie)
        except Exception:
            pass

    def _populate_all_details(self, movie):
        self.lbl_title.config(text=movie.get('title', 'No Title'))
        run_time = f"{movie.get('runtime', 0)} min" if movie.get('runtime') else "N/A"
        meta_text = f"{movie.get('year', 'N/A')}  |  {movie.get('rating', 0)}/10 ★  |  {run_time}"
        self.lbl_meta.config(text=meta_text)
        
        self.story_text.config(state="normal")
        self.story_text.delete("1.0", tk.END)
        
        desc = movie.get('description_full') or movie.get('description_intro') or movie.get('summary') or movie.get('synopsis')
        if not desc:
            desc = "No synopsis available (Try adding a TMDB API key in Settings)."
        
        self.story_text.insert(tk.END, desc)
        self.story_text.config(state="disabled")

        cast = movie.get('cast')
        if cast:
            if isinstance(cast[0], dict):
                names = [a.get('name', '') for a in cast]
            else:
                names = cast
            self.lbl_cast.config(text="Starring: " + ", ".join(names[:5]))
        else:
            self.lbl_cast.config(text="Starring: N/A")

        if 'trailer_key' in movie:
            self.trailer_btn.config(state="normal", command=lambda: webbrowser.open(f"https://www.youtube.com/watch?v={movie['trailer_key']}"))
        else:
            self.trailer_btn.config(state="disabled")

        for w in self.dl_scroll_frame.winfo_children():
            w.destroy()
            
        torrents = movie.get('torrents', [])
        if torrents:
            for t in torrents:
                card = ttk.Frame(self.dl_scroll_frame, style="Card.TFrame", relief="solid", borderwidth=1)
                card.pack(fill=tk.X, pady=2)
                
                lbl = ttk.Label(card, text=f"{t['quality']}  {t['type'].upper()}", font=FONT_BOLD, background=COLOR_BG_LIGHT, width=15)
                lbl.pack(side=tk.LEFT, padx=5, pady=5)
                
                ttk.Label(card, text=t['size'], background=COLOR_BG_LIGHT).pack(side=tk.LEFT, padx=5)
                
                btn = ttk.Button(card, text="⬇ Download", style="Accent.TButton", 
                           command=lambda t=t, title=movie['title']: self._download_torrent(t, title))
                btn.pack(side=tk.RIGHT, padx=5, pady=2)
        else:
            ttk.Label(self.dl_scroll_frame, text="No torrents found.", background=COLOR_BG_LIGHT).pack(pady=10)

        spec_text = f"IMDB Code: {movie.get('imdb_code', 'N/A')}\nLanguage: {movie.get('language', 'en').upper()}\nMPA Rating: {movie.get('mpa_rating', 'NR')}\n\nTorrent Stats:\n"
        for t in torrents:
             spec_text += f"• {t['quality']}: {t['seeds']} Seeds / {t['peers']} Peers\n"
        self.lbl_specs.config(text=spec_text)
        
        threading.Thread(target=self._load_poster_image, args=(movie,), daemon=True).start()

    def _load_poster_image(self, movie):
        url = movie.get('large_cover_image')
        if not url:
            self.current_poster_data = None
            self.root.after(0, self._set_placeholder_poster)
            return
        
        data = self.api.get_image_data(url)
        if not data or self.last_selected_movie_id != movie['id']:
            return
            
        self.current_poster_data = data
        self.root.after(0, lambda: self._apply_poster_image(data))

    def _apply_poster_image(self, data):
        try:
            MAX_HEIGHT = 250
            img_temp = Image.open(io.BytesIO(data))
            orig_w, orig_h = img_temp.size
            aspect_ratio = orig_w / orig_h
            
            target_h = MAX_HEIGHT
            target_w = int(target_h * aspect_ratio)
            
            img = img_temp.resize((target_w, target_h), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.poster_label.config(image=photo)
            self.poster_label.image = photo
        except:
            self._set_placeholder_poster()

    def _set_placeholder_poster(self):
        try:
            ph = resources.get_icon("placeholder", 64, 64)
            self.poster_label.config(image=ph)
            self.poster_label.image = ph
        except:
            pass

    def _clear_all_details(self):
        self.current_movie_details = None
        self._set_placeholder_poster()
        self.lbl_title.config(text="Select a Movie")
        self.lbl_meta.config(text="")
        
        self.story_text.config(state="normal")
        self.story_text.delete("1.0", tk.END)
        self.story_text.config(state="disabled")
        
        self.trailer_btn.config(state="disabled")
        for w in self.dl_scroll_frame.winfo_children():
            w.destroy()
        self.lbl_specs.config(text="")

    def _download_torrent(self, torrent, title):
        encoded = urllib.parse.quote(title)
        magnet = f"magnet:?xt=urn:btih:{torrent['hash']}&dn={encoded}"
        for tr in self.all_trackers:
            magnet += f"&tr={tr}"
            
        if messagebox.askyesno("Download", f"Open magnet link for:\n{title} [{torrent['quality']}]?"):
            webbrowser.open(magnet)

    def _update_pagination(self):
        self.page_label.config(text=f"Page {self.current_page} ({self.total_movie_count} found)")
        self.btn_prev.config(state=tk.NORMAL if self.current_page > 1 else tk.DISABLED)
        self.btn_next.config(state=tk.NORMAL if (self.current_page*50) < self.total_movie_count else tk.DISABLED)

    def _prev_page(self):
        if self.current_page > 1:
            self._on_search(self.current_page - 1)

    def _next_page(self):
        self._on_search(self.current_page + 1)
    
    def _show_error(self, msg):
        messagebox.showerror("Error", msg)
        self.status_label.place_forget()

    def _set_ui_state(self, state):
        for child in self.filter_frame.winfo_children():
            if isinstance(child, (ttk.Button, ttk.Entry, ttk.Combobox, ttk.Checkbutton)):
                try:
                    child.config(state=state)
                except:
                    pass
        self.btn_prev.config(state=state)
        self.btn_next.config(state=state)
        if state == tk.NORMAL:
            self._update_pagination()

if __name__ == "__main__":
    root = tk.Tk()
    app = MovieApp(root)
    root.mainloop()
