import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import threading
import webbrowser
import urllib.parse
import io
import json
import configparser
from api_handler import APIHandler
import resources

# --- Constants ---
BASE_GEOMETRY = "1000x650"; BASE_POSTER_WIDTH = 220
YTS_DOMAINS_FILE = "yts_domains.json"; APP_CONFIG_FILE = "config.ini"
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

# --- Editor Windows ---

class ApiKeyEditorWindow(tk.Toplevel):
    """A separate modal window for editing the TMDB API key."""
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.title("Set API Keys")
        self.geometry("450x180")
        self.transient(parent); self.grab_set()
        self.callback = callback

        ttk.Label(self, text="Enter your TMDB API Key (v3 Auth) below:", wraplength=430).pack(padx=10, pady=10)
        self.api_key_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.api_key_var, width=60).pack(padx=10, pady=5)
        
        ttk.Separator(self, orient='horizontal').pack(fill='x', pady=10, padx=10)
        
        button_frame = ttk.Frame(self, padding=10)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Save", command=self._on_save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)

        self._load_key()

    def _load_key(self):
        try:
            config = configparser.ConfigParser()
            config.read(APP_CONFIG_FILE)
            key = config.get('TMDB', 'api_key', fallback="")
            self.api_key_var.set(key)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load config file:\n{e}", parent=self)
            
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
            messagebox.showinfo("Success", "API Key saved. The new settings will be used for the next movie selected.", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config file:\n{e}", parent=self)


class DomainEditorWindow(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.title("Edit YTS Domains"); self.geometry("400x500")
        self.transient(parent); self.grab_set(); self.callback = callback
        ttk.Label(self, text="Edit the list of YTS domains below (one per line):", wraplength=380).pack(padx=10, pady=10)
        text_frame = ttk.Frame(self); text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.text_editor = tk.Text(text_frame, wrap="word", font=("Segoe UI", 10))
        self.scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_editor.yview)
        self.text_editor.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y); self.text_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        button_frame = ttk.Frame(self, padding=10); button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Save and Close", command=self._on_save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        self._load_domains()

    def _load_domains(self):
        try:
            with open(YTS_DOMAINS_FILE, 'r') as f: self.text_editor.insert(tk.END, "\n".join(json.load(f)))
        except (FileNotFoundError, json.JSONDecodeError) as e: self.text_editor.insert(tk.END, f"# Could not load domains: {e}")

    def _on_save(self):
        raw_text = self.text_editor.get("1.0", tk.END); domains = [line.strip() for line in raw_text.split("\n") if line.strip()]
        try:
            with open(YTS_DOMAINS_FILE, 'w') as f: json.dump(domains, f, indent=4)
            self.callback(); messagebox.showinfo("Success", "YTS domains have been updated.", parent=self); self.destroy()
        except Exception as e: messagebox.showerror("Error", f"Failed to save domains file:\n{e}", parent=self)

# --- Main Application Class ---

class MovieApp:
    def __init__(self, root):
        self.root = root; self.root.title("Movie Explorer"); self.root.geometry(BASE_GEOMETRY); self.root.minsize(800, 500)
        self.root.iconphoto(True, resources.get_app_icon())
        self.api = APIHandler(); self.movies_cache = []; self.current_movie_details = None; self.current_page = 1
        self.total_movie_count = 0; self.last_selected_movie_id = None; self._resize_job = None
        self.last_sort = {'col': None, 'rev': False}
        self._setup_styles(); self._setup_ui(); self._on_search(); self.details_frame.bind('<Configure>', self._on_panel_resize)

    def _setup_styles(self):
        style = ttk.Style(); style.configure("TFrame", background="#f0f0f0"); style.configure("TLabel", background="#f0f0f0", font=('Segoe UI', 9))
        style.configure("TButton", font=('Segoe UI', 9)); style.configure("Treeview.Heading", font=('Segoe UI', 10, 'bold'))
        style.configure("Title.TLabel", font=('Segoe UI', 11, 'bold'), wraplength=300); style.configure("Accent.TButton", font=('Segoe UI', 10, 'bold'))
        style.configure("Trailer.TButton", foreground="red")

    def _setup_ui(self):
        main_paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL); main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        filter_frame = self._create_filter_panel(main_paned_window); results_frame = self._create_results_panel(main_paned_window); details_frame = self._create_details_panel(main_paned_window)
        main_paned_window.add(filter_frame, weight=1); main_paned_window.add(results_frame, weight=4); main_paned_window.add(details_frame, weight=2)

    def _create_filter_panel(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Search Filters", font=('Segoe UI', 12, 'bold')).pack(fill=tk.X, pady=(0, 10))
        ttk.Label(frame, text="Movie Title:").pack(fill=tk.X, pady=(5, 2)); self.search_term = tk.StringVar(); ttk.Entry(frame, textvariable=self.search_term).pack(fill=tk.X)
        ttk.Label(frame, text="Genre:").pack(fill=tk.X, pady=(10, 2)); self.genre = tk.StringVar(value='All'); ttk.Combobox(frame, textvariable=self.genre, values=GENRES, state='readonly').pack(fill=tk.X)
        ttk.Label(frame, text="Quality:").pack(fill=tk.X, pady=(10, 2)); self.quality = tk.StringVar(value='All'); ttk.Combobox(frame, textvariable=self.quality, values=QUALITIES, state='readonly').pack(fill=tk.X)
        ttk.Label(frame, text="Minimum Rating:").pack(fill=tk.X, pady=(10, 2)); self.rating = tk.IntVar(value=0); ttk.Combobox(frame, textvariable=self.rating, values=RATINGS, state='readonly').pack(fill=tk.X)
        ttk.Label(frame, text="Sort By:").pack(fill=tk.X, pady=(10, 2)); self.sort_by = tk.StringVar(value='date_added'); ttk.Combobox(frame, textvariable=self.sort_by, values=SORT_BY, state='readonly').pack(fill=tk.X)
        self.order_by = tk.StringVar(value='desc'); ttk.Checkbutton(frame, text="Ascending Order", variable=self.order_by, onvalue='asc', offvalue='desc').pack(fill=tk.X, pady=5)
        search_icon = resources.get_icon("search", 16, 16); ttk.Button(frame, text=" Search", command=self._on_search, style="Accent.TButton", image=search_icon, compound=tk.LEFT).pack(fill=tk.X, pady=(20,5), ipady=5)
        
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)
        
        ttk.Button(frame, text="Edit YTS Domains...", command=self._open_domain_editor).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="Set API Keys...", command=self._open_api_key_editor).pack(fill=tk.X, pady=2)
        
        return frame

    def _create_results_panel(self, parent):
        frame = ttk.Frame(parent, padding=5); columns = ("title", "year", "rating", "genre"); self.tree = ttk.Treeview(frame, columns=columns, show='headings')
        self.tree.heading("title", text="Title", command=lambda: self._sort_column("title")); self.tree.heading("year", text="Year", command=lambda: self._sort_column("year"))
        self.tree.heading("rating", text="Rating", command=lambda: self._sort_column("rating")); self.tree.heading("genre", text="Genre", command=lambda: self._sort_column("genre"))
        self.tree.column("title", width=300, minwidth=200); self.tree.column("year", width=60, anchor='center'); self.tree.column("rating", width=60, anchor='center'); self.tree.column("genre", width=120, minwidth=100)
        self.tree.pack(fill=tk.BOTH, expand=True); self.tree.bind("<<TreeviewSelect>>", self._on_movie_select)
        nav_frame = ttk.Frame(frame); nav_frame.pack(fill=tk.X, pady=5); prev_icon = resources.get_icon("prev", 16, 16); next_icon = resources.get_icon("next", 16, 16)
        self.btn_prev = ttk.Button(nav_frame, text=" Prev", command=self._prev_page, state=tk.DISABLED, image=prev_icon, compound=tk.LEFT); self.btn_prev.pack(side=tk.LEFT)
        self.page_label = ttk.Label(nav_frame, text="Page 1", anchor='center'); self.page_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_next = ttk.Button(nav_frame, text="Next ", command=self._next_page, state=tk.DISABLED, image=next_icon, compound=tk.RIGHT); self.btn_next.pack(side=tk.RIGHT)
        return frame

    def _create_details_panel(self, parent):
        frame = ttk.Frame(parent, padding=10); self.details_frame = frame
        placeholder_icon = resources.get_icon("placeholder", 64, 64); self.poster_label = ttk.Label(frame, background='#333333', anchor=tk.CENTER, image=placeholder_icon)
        self.poster_label.pack(pady=5, fill=tk.X); self.poster_label.image = placeholder_icon
        self.trailer_button = ttk.Button(frame, text="▶️ Watch Trailer", style="Trailer.TButton"); self.cast_frame = ttk.Frame(frame)
        self.title_year_label = ttk.Label(frame, text="Select a Movie", style="Title.TLabel"); self.title_year_label.pack(fill=tk.X, pady=5)
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(frame, text="Available Torrents:", font=('Segoe UI', 10, 'bold')).pack(fill=tk.X, pady=(5, 5)); self.torrents_frame = ttk.Frame(frame)
        self.torrents_frame.pack(fill=tk.BOTH, expand=True)
        return frame

    def _open_domain_editor(self):
        DomainEditorWindow(self.root, callback=self._on_domains_updated)
    def _open_api_key_editor(self):
        ApiKeyEditorWindow(self.root, callback=self._on_api_key_updated)

    def _on_domains_updated(self):
        self.api.reload_yts_domains()
        messagebox.showinfo("Domains Reloaded", "The YTS domain list has been updated. The next search will use the new list.")
    def _on_api_key_updated(self):
        self.api.reload_app_config()

    def _sort_column(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        def get_sort_key(item):
            value = item[0]
            if col in ['year', 'rating']:
                try: return float(value)
                except (ValueError, TypeError): return 0.0
            return value.lower()
        reverse = self.last_sort['col'] == col and not self.last_sort['rev']; self.last_sort = {'col': col, 'rev': reverse}; items.sort(key=get_sort_key, reverse=reverse)
        for index, (val, k) in enumerate(items): self.tree.move(k, '', index)

    def _on_panel_resize(self, event):
        if self._resize_job: self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(300, self._resize_poster_job)

    def _resize_poster_job(self):
        if self.current_movie_details: self._update_details_panel(self.current_movie_details)
    
    def _on_search(self, page=1):
        self.current_page = page; self.last_selected_movie_id = None; self._set_ui_state(tk.DISABLED)
        threading.Thread(target=self._perform_search, daemon=True).start()

    def _perform_search(self):
        try:
            params = {'page': self.current_page, 'sort_by': self.sort_by.get(), 'order_by': self.order_by.get()}; query = self.search_term.get(); genre = self.genre.get(); quality = self.quality.get(); rating = self.rating.get()
            if query: params['query_term'] = query
            if genre != 'All': params['genre'] = genre
            if quality != 'All': params['quality'] = quality
            if rating > 0: params['minimum_rating'] = rating
            data = self.api.list_movies(**params)
            self.total_movie_count = data.get('movie_count', 0)
            self.root.after(0, self._update_results_list, data.get('movies', []))
        except Exception as e:
            self.root.after(0, self._show_error, str(e))
        finally:
            self.root.after(0, self._set_ui_state, tk.NORMAL)

    def _update_results_list(self, movies):
        self.tree.delete(*self.tree.get_children()); self.movies_cache = movies
        if not movies: self._clear_details_panel()
        else:
            for movie in movies:
                genres = ', '.join(movie.get('genres', ['N/A'])[:2])
                self.tree.insert("", tk.END, iid=movie['id'], values=(movie['title'], movie['year'], movie['rating'], genres))
            first_movie_id = self.tree.get_children()[0]; self.tree.selection_set(first_movie_id); self.tree.focus(first_movie_id)
        self._update_pagination()
    
    def _on_movie_select(self, event=None):
        selection = self.tree.selection();
        if not selection: return
        movie_id = int(selection[0]);
        if movie_id == self.last_selected_movie_id: return
        self.last_selected_movie_id = movie_id; self._clear_details_panel(); threading.Thread(target=self._load_movie_details, args=(movie_id,), daemon=True).start()
    
    def _load_movie_details(self, movie_id):
        try:
            yts_details = self.api.get_movie_details(movie_id)
            if not yts_details or self.last_selected_movie_id != movie_id: return
            movie_data = yts_details['movie']; imdb_id = movie_data.get('imdb_code'); enhanced_details = self.api.get_tmdb_details(imdb_id)
            if enhanced_details: movie_data.update(enhanced_details)
            self.current_movie_details = movie_data; self.root.after(0, self._update_details_panel, self.current_movie_details)
        except Exception as e:
            self.root.after(0, self._show_error, f"Could not load movie details: {e}")

    def _update_details_panel(self, movie):
        title_year_text = f"{movie.get('title', 'No Title')} ({movie.get('year', 'N/A')})"; self.title_year_label.config(text=title_year_text, wraplength=self.details_frame.winfo_width() - 20)
        if 'trailer_key' in movie:
            trailer_key = movie['trailer_key']; self.trailer_button.configure(command=lambda: webbrowser.open(f"https://www.youtube.com/watch?v={trailer_key}"))
            self.trailer_button.pack(fill=tk.X, pady=5, before=self.title_year_label)
        else: self.trailer_button.pack_forget()
        for widget in self.cast_frame.winfo_children(): widget.destroy()
        cast_list = movie.get('cast')
        if cast_list:
            ttk.Label(self.cast_frame, text="Starring:", font=('Segoe UI', 9, 'bold')).pack(anchor='w')
            if cast_list and isinstance(cast_list[0], dict): names = [actor.get('name', '') for actor in cast_list]; cast_text = ", ".join(names)
            else: cast_text = ", ".join(cast_list)
            ttk.Label(self.cast_frame, text=cast_text, wraplength=self.details_frame.winfo_width() - 20).pack(anchor='w')
            self.cast_frame.pack(fill=tk.X, pady=5, before=self.title_year_label)
        else: self.cast_frame.pack_forget()
        for widget in self.torrents_frame.winfo_children(): widget.destroy()
        if movie.get('torrents'):
            for torrent in movie['torrents']:
                text = f"{torrent['quality']} ({torrent['type']}) - {torrent['size']} | Seeds: {torrent['seeds']}"
                ttk.Button(self.torrents_frame, text=text, command=lambda t=torrent, title=movie['title']: self._download_torrent(t, title)).pack(fill=tk.X, pady=2)
        else: ttk.Label(self.torrents_frame, text="No torrents available.").pack()
        threading.Thread(target=self._update_poster_image, args=(movie,), daemon=True).start()
    
    def _update_poster_image(self, movie):
        poster_url = movie.get('large_cover_image');
        if not poster_url: self.root.after(0, self._set_placeholder_poster); return
        image_data = self.api.get_image_data(poster_url)
        if not image_data or self.last_selected_movie_id != movie['id']: return
        try:
            panel_width = self.details_frame.winfo_width() - 20;
            if panel_width < 50: panel_width = BASE_POSTER_WIDTH
            new_width = panel_width; new_height = int(new_width * 1.5)
            img = Image.open(io.BytesIO(image_data)).resize((new_width, new_height), Image.Resampling.LANCZOS); photo = ImageTk.PhotoImage(img)
            self.root.after(0, lambda: self._apply_poster_image(photo))
        except Exception as e:
            print(f"Error processing poster image: {e}"); self.root.after(0, self._set_placeholder_poster)

    def _clear_details_panel(self):
        self.current_movie_details = None; self._set_placeholder_poster(); self.title_year_label.config(text="Select a Movie")
        self.trailer_button.pack_forget(); self.cast_frame.pack_forget()
        for widget in self.cast_frame.winfo_children(): widget.destroy()
        for widget in self.torrents_frame.winfo_children(): widget.destroy()

    def _set_placeholder_poster(self):
        placeholder_icon = resources.get_icon("placeholder", 64, 64); self.poster_label.config(image=placeholder_icon, background='#333333'); self.poster_label.image = placeholder_icon
    def _apply_poster_image(self, photo_image):
        self.poster_label.config(image=photo_image, background='#f0f0f0'); self.poster_label.image = photo_image
    def _update_pagination(self):
        self.page_label.config(text=f"Page {self.current_page} ({self.total_movie_count} results)")
        self.btn_prev.config(state=tk.NORMAL if self.current_page > 1 else tk.DISABLED)
        has_more_pages = (self.current_page * 50) < self.total_movie_count; self.btn_next.config(state=tk.NORMAL if has_more_pages else tk.DISABLED)

    def _prev_page(self):
        if self.current_page > 1: self._on_search(page=self.current_page - 1)
    def _next_page(self):
        self._on_search(page=self.current_page + 1)

    def _download_torrent(self, torrent, title):
        encoded_title = urllib.parse.quote(title); magnet_link = f"magnet:?xt=urn:btih:{torrent['hash']}&dn={encoded_title}"
        for tracker in DEFAULT_TRACKERS: magnet_link += f"&tr={tracker}"
        if messagebox.askokcancel("Confirm Download", f"Open magnet link for:\n\n{title} ({torrent['quality']})"):
            webbrowser.open(magnet_link)
    
    def _show_error(self, message):
        messagebox.showerror("Error", message)
    
    def _set_ui_state(self, state):
        filter_panel = self.root.winfo_children()[0].winfo_children()[0]
        for widget in filter_panel.winfo_children():
            if isinstance(widget, (ttk.Button, ttk.Combobox, ttk.Entry, ttk.Checkbutton)):
                widget.config(state=state)
        self.btn_next.config(state=state); self.btn_prev.config(state=state)
        if state == tk.NORMAL: self._update_pagination()

if __name__ == "__main__":
    root = tk.Tk()
    app = MovieApp(root)
    root.mainloop()
