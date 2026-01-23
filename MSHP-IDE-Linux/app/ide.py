from __future__ import annotations

import builtins
import io
import keyword
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tokenize

ROOT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT_DIR / '.runtime'
PYTHON_DIR = ROOT_DIR / 'python'

EDITOR_FONT = ('Consolas', 12)
CONSOLE_FONT = ('Consolas', 11)
LINE_NUMBER_FONT = ('Consolas', 10)
INPUT_FONT = ('Consolas', 11)

INPUT_PREFIX = '> '

HIGHLIGHT_DELAY_MS = 200
POLL_DELAY_MS = 50
TURTLE_UI_PUMP_INTERVAL = 0.02

THEMES = {
    'light': {
        'app_bg': '#f5f9ff',
        'panel_bg': '#ffffff',
        'toolbar_bg': '#e7f0ff',
        'accent': '#2563eb',
        'accent_dark': '#1d4ed8',
        'menu_bg': '#e7f0ff',
        'menu_fg': '#0f172a',
        'menu_active_bg': '#dbeafe',
        'menu_active_fg': '#1d4ed8',
        'run_bg': '#16a34a',
        'run_bg_active': '#22c55e',
        'stop_bg': '#dc2626',
        'stop_bg_active': '#ef4444',
        'stop_bg_disabled': '#f3c6c6',
        'stop_fg_disabled': '#7f1d1d',
        'editor_bg': '#ffffff',
        'editor_fg': '#0f172a',
        'console_bg': '#f8fbff',
        'console_fg': '#0f172a',
        'line_number_bg': '#e7f0ff',
        'line_number_fg': '#3b82f6',
        'input_bg': '#ffffff',
        'input_bg_focus': '#eff6ff',
        'input_fg': '#0f172a',
        'selection_bg': '#dbeafe',
        'selection_fg': '#0f172a',
        'status_fg': '#1e40af',
        'stderr_fg': '#dc2626',
        'stdin_fg': '#0ea5a4',
        'scrollbar_bg': '#cbd5f5',
        'scrollbar_trough': '#e7f0ff',
        'check_bg': '#f5f9ff',
        'check_fg': '#0f172a',
        'syntax_comment': '#64748b',
        'syntax_string': '#1d4ed8',
        'syntax_number': '#0ea5e9',
        'syntax_keyword': '#1e40af',
        'syntax_builtin': '#0369a1',
        'syntax_error': '#dc2626',
    },
    'dark': {
        'app_bg': '#0b1220',
        'panel_bg': '#0f172a',
        'toolbar_bg': '#111c33',
        'accent': '#60a5fa',
        'accent_dark': '#3b82f6',
        'menu_bg': '#111c33',
        'menu_fg': '#e2e8f0',
        'menu_active_bg': '#1e293b',
        'menu_active_fg': '#f8fafc',
        'run_bg': '#16a34a',
        'run_bg_active': '#22c55e',
        'stop_bg': '#ef4444',
        'stop_bg_active': '#f87171',
        'stop_bg_disabled': '#3b1f1f',
        'stop_fg_disabled': '#a1a1aa',
        'editor_bg': '#0f172a',
        'editor_fg': '#e2e8f0',
        'console_bg': '#0b1325',
        'console_fg': '#e2e8f0',
        'line_number_bg': '#111c33',
        'line_number_fg': '#60a5fa',
        'input_bg': '#0f172a',
        'input_bg_focus': '#111827',
        'input_fg': '#e2e8f0',
        'selection_bg': '#1e293b',
        'selection_fg': '#f8fafc',
        'status_fg': '#93c5fd',
        'stderr_fg': '#fca5a5',
        'stdin_fg': '#22d3ee',
        'scrollbar_bg': '#334155',
        'scrollbar_trough': '#0f172a',
        'check_bg': '#0b1220',
        'check_fg': '#e2e8f0',
        'syntax_comment': '#94a3b8',
        'syntax_string': '#93c5fd',
        'syntax_number': '#38bdf8',
        'syntax_keyword': '#60a5fa',
        'syntax_builtin': '#7dd3fc',
        'syntax_error': '#f87171',
    },
}


def read_text_file(path: Path) -> str:
    for encoding in ('utf-8', 'utf-8-sig', 'cp1251', 'latin-1'):
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            continue
    return path.read_text(errors='replace')


def find_python_in_dir(base_dir: Path) -> Path | None:
    if os.name == 'nt':
        names = ['python.exe']
        patterns = ['python-*/python.exe', 'WPy*/python-*/python.exe']
        search_name = 'python.exe'
    else:
        names = ['python3', 'python']
        patterns = [
            'python-*/bin/python3',
            'python-*/bin/python',
            '*/bin/python3',
            '*/bin/python',
        ]
        search_name = 'python3'

    for name in names:
        direct = base_dir / name
        if direct.exists():
            return direct

    for pattern in patterns:
        for candidate in base_dir.glob(pattern):
            if candidate.exists():
                return candidate

    candidates = [p for p in base_dir.rglob(search_name) if p.is_file()]
    if os.name != 'nt':
        candidates.extend([p for p in base_dir.rglob('python') if p.is_file()])
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: len(str(path)))[0]


def get_python_executable() -> str | None:
    env_path = os.environ.get('PYTHON_PORTABLE')
    if env_path and Path(env_path).exists():
        return env_path
    candidate = find_python_in_dir(PYTHON_DIR)
    if candidate:
        return str(candidate)
    return None


class EditorTab:
    def __init__(self, app: 'PortableIDE', path: Path | None = None) -> None:
        self.app = app
        self.path = path
        self.virtual_name: str | None = None
        self.modified = False
        self.highlight_job = None
        self.line_job = None

        self.frame = ttk.Frame(app.notebook, style='Editor.TFrame')
        self.line_numbers = tk.Canvas(
            self.frame,
            width=48,
            highlightthickness=0,
            bd=0,
        )
        self.line_numbers.pack(side='left', fill='y')

        self.text = tk.Text(
            self.frame,
            wrap='none',
            undo=True,
            font=EDITOR_FONT,
            tabs=('1c',),
        )
        self.text.pack(fill='both', expand=True, side='left')

        self.y_scroll = ttk.Scrollbar(self.frame, orient='vertical', command=self._on_text_scroll)
        self.text.configure(yscrollcommand=self._on_text_yscroll)
        self.y_scroll.pack(fill='y', side='right')

        self.text.bind('<<Modified>>', self.on_modified)
        self.text.bind('<KeyRelease>', self.on_key_release)
        self.text.bind('<MouseWheel>', self.on_scroll_event)
        self.text.bind('<Button-4>', self.on_scroll_event)
        self.text.bind('<Button-5>', self.on_scroll_event)
        self.text.bind('<Configure>', self.on_scroll_event)
        self.text.bind('<Tab>', lambda e: self.app._indent_or_tab(self.text))

        self.app.bind_text_shortcuts(self.text)
        self.apply_theme()
        self._update_line_numbers()

    def apply_theme(self) -> None:
        theme = self.app.theme
        self.line_numbers.configure(background=theme['line_number_bg'])
        self.text.configure(
            background=theme['editor_bg'],
            foreground=theme['editor_fg'],
            insertbackground=theme['editor_fg'],
            selectbackground=theme['selection_bg'],
            selectforeground=theme['selection_fg'],
        )
        self._setup_tags()
        self._update_line_numbers()

    def _setup_tags(self) -> None:
        theme = self.app.theme
        self.text.tag_configure('comment', foreground=theme['syntax_comment'])
        self.text.tag_configure('string', foreground=theme['syntax_string'])
        self.text.tag_configure('number', foreground=theme['syntax_number'])
        self.text.tag_configure('keyword', foreground=theme['syntax_keyword'], font=('Consolas', 12, 'bold'))
        self.text.tag_configure('builtin', foreground=theme['syntax_builtin'])
        self.text.tag_configure('error', foreground=theme['syntax_error'])

    def on_modified(self, _event=None) -> None:
        if self.text.edit_modified():
            self.modified = True
            self.app.update_tab_title(self)
            self.text.edit_modified(False)
            self.schedule_highlight()
            self.schedule_line_numbers()

    def on_key_release(self, _event=None) -> None:
        self.schedule_highlight()
        self.schedule_line_numbers()

    def on_scroll_event(self, _event=None) -> None:
        self.schedule_line_numbers()

    def schedule_line_numbers(self) -> None:
        if self.line_job is not None:
            self.text.after_cancel(self.line_job)
        self.line_job = self.text.after(30, self._update_line_numbers)

    def _on_text_yscroll(self, first: str, last: str) -> None:
        self.y_scroll.set(first, last)
        self._update_line_numbers()

    def _on_text_scroll(self, *args) -> None:
        self.text.yview(*args)
        self._update_line_numbers()

    def _update_line_numbers(self) -> None:
        self.line_job = None
        self.line_numbers.delete('all')
        line = self.text.index('@0,0')
        theme = self.app.theme
        while True:
            dline = self.text.dlineinfo(line)
            if dline is None:
                break
            y = dline[1]
            line_number = str(line).split('.')[0]
            self.line_numbers.create_text(
                4,
                y,
                anchor='nw',
                text=line_number,
                fill=theme['line_number_fg'],
                font=LINE_NUMBER_FONT,
            )
            line = self.text.index(f'{line}+1line')

    def schedule_highlight(self) -> None:
        if self.highlight_job is not None:
            self.text.after_cancel(self.highlight_job)
        self.highlight_job = self.text.after(HIGHLIGHT_DELAY_MS, self.apply_highlight)

    def apply_highlight(self) -> None:
        self.highlight_job = None
        code = self.text.get('1.0', 'end-1c')
        for tag in ('comment', 'string', 'number', 'keyword', 'builtin', 'error'):
            self.text.tag_remove(tag, '1.0', 'end')

        if not code.strip():
            return

        try:
            tokens = tokenize.generate_tokens(io.StringIO(code).readline)
            for token_type, token_string, start, end, _line in tokens:
                start_index = f"{start[0]}.{start[1]}"
                end_index = f"{end[0]}.{end[1]}"
                if token_type == tokenize.COMMENT:
                    self.text.tag_add('comment', start_index, end_index)
                elif token_type == tokenize.STRING:
                    self.text.tag_add('string', start_index, end_index)
                elif token_type == tokenize.NUMBER:
                    self.text.tag_add('number', start_index, end_index)
                elif token_type == tokenize.NAME:
                    if token_string in keyword.kwlist:
                        self.text.tag_add('keyword', start_index, end_index)
                    elif token_string in dir(builtins):
                        self.text.tag_add('builtin', start_index, end_index)
        except Exception:
            self.text.tag_add('error', '1.0', 'end')
            return

    def set_content(self, content: str) -> None:
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', content)
        self.text.edit_modified(False)
        self.modified = False
        self.app.update_tab_title(self)
        self.apply_highlight()
        self._update_line_numbers()

    def get_content(self) -> str:
        return self.text.get('1.0', 'end-1c')


class PortableIDE(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title('Портативная Python IDE 🐍')
        self.geometry('1100x700')

        self.process: subprocess.Popen[str] | None = None
        self.output_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.dark_mode = tk.BooleanVar(value=False)
        self.save_on_run_preference: bool | None = None
        self.turtle_screen = None
        self.turtle_visible = False
        self.turtle_running = False
        self.turtle_abort = False
        self._turtle_custom_coords = False
        self._turtle_setworld = None
        self._turtle_initialized = False
        self._closing = False
        self._main_created = False
        self._module_counter = 0
        self.save_before_run_var = tk.StringVar(value='ask')
        self.main_tab: EditorTab | None = None

        self.theme = THEMES['dark' if self.dark_mode.get() else 'light']

        self._apply_style()
        self._build_ui()
        self._bind_shortcuts()
        self.after(POLL_DELAY_MS, self._poll_output)

        self.new_tab()
        self.after(100, self._focus_editor)

    def _apply_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass

        theme = self.theme
        self.configure(background=theme['app_bg'])
        style.configure('TFrame', background=theme['app_bg'])
        style.configure('Editor.TFrame', background=theme['panel_bg'])
        style.configure('Toolbar.TFrame', background=theme['toolbar_bg'])
        style.configure('Runbar.TFrame', background=theme['app_bg'])
        style.configure('TLabel', background=theme['app_bg'], foreground=theme['editor_fg'])
        style.configure(
            'TCheckbutton',
            background=theme['check_bg'],
            foreground=theme['check_fg'],
        )
        style.map(
            'TCheckbutton',
            background=[('active', theme['toolbar_bg'])],
            foreground=[('active', theme['accent'])],
        )
        style.configure(
            'TScrollbar',
            background=theme['scrollbar_bg'],
            troughcolor=theme['scrollbar_trough'],
            bordercolor=theme['scrollbar_trough'],
            arrowcolor=theme['editor_fg'],
        )
        style.configure('Toolbar.TButton', background=theme['accent'], foreground='white', padding=(12, 6), borderwidth=0)
        style.map(
            'Toolbar.TButton',
            background=[('active', theme['accent_dark'])],
            foreground=[('active', 'white')],
        )
        style.configure('Run.TButton', background=theme['run_bg'], foreground='white', padding=(14, 6), borderwidth=0)
        style.map(
            'Run.TButton',
            background=[('active', theme['run_bg_active'])],
            foreground=[('active', 'white')],
        )
        style.configure('Stop.TButton', background=theme['stop_bg'], foreground='white', padding=(14, 6), borderwidth=0)
        style.map(
            'Stop.TButton',
            background=[('disabled', theme['stop_bg_disabled']), ('active', theme['stop_bg_active'])],
            foreground=[('disabled', theme['stop_fg_disabled']), ('active', 'white')],
        )
        style.configure('TNotebook', background=theme['app_bg'], borderwidth=0)
        style.configure(
            'TNotebook.Tab',
            background=theme['toolbar_bg'],
            foreground=theme['editor_fg'],
            padding=(10, 4),
        )
        style.map(
            'TNotebook.Tab',
            background=[('selected', theme['panel_bg'])],
            foreground=[('selected', theme['accent'])],
        )

    def _apply_theme(self) -> None:
        self.theme = THEMES['dark' if self.dark_mode.get() else 'light']
        self._apply_style()

        theme = self.theme
        self.console.configure(
            background=theme['console_bg'],
            foreground=theme['console_fg'],
            insertbackground=theme['console_fg'],
            selectbackground=theme['selection_bg'],
            selectforeground=theme['selection_fg'],
        )
        self.console.tag_configure('stdout', foreground=theme['console_fg'])
        self.console.tag_configure('stderr', foreground=theme['stderr_fg'])
        self.console.tag_configure('status', foreground=theme['status_fg'])
        self.console.tag_configure('stdin', foreground=theme['stdin_fg'])

        self.input_text.configure(
            background=theme['input_bg'],
            foreground=theme['input_fg'],
            insertbackground=theme['input_fg'],
            highlightbackground=theme['accent'],
            highlightcolor=theme['accent'],
            selectbackground=theme['selection_bg'],
            selectforeground=theme['selection_fg'],
        )

        for tab in self.tabs_by_frame.values():
            tab.apply_theme()

        self.turtle_canvas.configure(
            background=theme['panel_bg'],
            highlightbackground=theme['accent'],
            highlightcolor=theme['accent_dark'],
        )

        self._apply_menu_theme()
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.configure(background=theme['app_bg'])

    def _build_ui(self) -> None:
        self._create_menu()

        file_toolbar = ttk.Frame(self, style='Toolbar.TFrame')
        file_toolbar.pack(fill='x')
        ttk.Button(file_toolbar, text='🆕 Новый', command=self.new_tab, style='Toolbar.TButton').pack(
            side='left', padx=4, pady=6
        )
        ttk.Button(file_toolbar, text='📂 Открыть', command=self.open_file, style='Toolbar.TButton').pack(
            side='left', padx=4, pady=6
        )
        ttk.Button(file_toolbar, text='💾 Сохранить', command=self.save_file, style='Toolbar.TButton').pack(
            side='left', padx=4, pady=6
        )
        ttk.Button(file_toolbar, text='🗜️ Архив', command=self.save_archive, style='Toolbar.TButton').pack(
            side='left', padx=4, pady=6
        )
        ttk.Button(file_toolbar, text='❌ Закрыть', command=self.close_current_tab, style='Toolbar.TButton').pack(
            side='left', padx=4, pady=6
        )

        run_toolbar = ttk.Frame(self, style='Runbar.TFrame')
        run_toolbar.pack(fill='x')
        ttk.Label(run_toolbar, text='Запуск', font=('Consolas', 11, 'bold')).pack(side='left', padx=(8, 6), pady=6)
        self.run_button = ttk.Button(
            run_toolbar,
            text='▶️ Запустить main.py (F5)',
            command=self.run_current,
            style='Run.TButton',
        )
        self.run_button.pack(side='left', padx=4, pady=6)
        self.stop_button = ttk.Button(
            run_toolbar,
            text='⏹ Остановить',
            command=self.stop_process,
            style='Stop.TButton',
        )
        self.stop_button.pack(side='left', padx=4, pady=6)

        ttk.Checkbutton(
            run_toolbar,
            text='Тёмная тема',
            variable=self.dark_mode,
            command=self._apply_theme,
        ).pack(side='right', padx=8, pady=6)

        self.paned = ttk.Panedwindow(self, orient='vertical')
        self.paned.pack(fill='both', expand=True)

        editor_frame = ttk.Frame(self.paned, style='Editor.TFrame')
        self.editor_paned = ttk.Panedwindow(editor_frame, orient='horizontal')
        self.editor_paned.pack(fill='both', expand=True)

        editor_main = ttk.Frame(self.editor_paned, style='Editor.TFrame')
        self.notebook = ttk.Notebook(editor_main)
        self.notebook.pack(fill='both', expand=True)
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)
        self.editor_paned.add(editor_main, weight=3)

        self.turtle_frame = ttk.Frame(self.editor_paned, style='Editor.TFrame')
        self.turtle_canvas = tk.Canvas(self.turtle_frame, highlightthickness=1, takefocus=1)
        self.turtle_canvas.pack(fill='both', expand=True, padx=6, pady=6)
        self.turtle_canvas.bind('<Button-1>', lambda _e: self.turtle_canvas.focus_set())
        self.turtle_canvas.bind('<Configure>', self._on_turtle_canvas_resize)

        self.paned.add(editor_frame, weight=3)

        self.input_frame = ttk.Frame(self.paned)
        input_label = ttk.Label(self.input_frame, text='Ввод (Enter — отправить, Ctrl+Enter — новая строка):')
        input_label.pack(side='top', anchor='w', padx=8, pady=(6, 0))
        self.input_text = tk.Text(
            self.input_frame,
            height=3,
            wrap='word',
            font=INPUT_FONT,
            relief='solid',
            bd=1,
            highlightthickness=1,
        )
        self.input_text.pack(fill='x', expand=True, padx=8, pady=6)
        self.input_text.bind('<Return>', self._send_console_input)
        self.input_text.bind('<Control-Return>', self._insert_input_newline)
        self.input_text.bind('<FocusIn>', self._on_input_focus_in)
        self.input_text.bind('<FocusOut>', self._on_input_focus_out)
        self._bind_input_shortcuts()
        self.paned.add(self.input_frame, weight=0)

        console_frame = ttk.Frame(self.paned)
        self.console = tk.Text(
            console_frame,
            height=10,
            wrap='word',
            font=CONSOLE_FONT,
            state='disabled',
        )
        self.console.bind('<Control-c>', self._console_copy)
        self.console.bind('<Control-C>', self._console_copy)
        self.console.pack(fill='both', expand=True, side='left')

        console_scroll = ttk.Scrollbar(console_frame, orient='vertical', command=self.console.yview)
        self.console.configure(yscrollcommand=console_scroll.set)
        console_scroll.pack(fill='y', side='right')

        self.paned.add(console_frame, weight=1)

        self.tabs_by_frame: dict[str, EditorTab] = {}
        self._apply_theme()
        self._update_input_state()
        self._update_run_controls()

    def _create_menu(self) -> None:
        self.menubar = tk.Menu(self)

        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(label='🆕 Новый', command=self.new_tab)
        self.file_menu.add_command(label='📂 Открыть…', command=self.open_file)
        self.file_menu.add_command(label='💾 Сохранить', command=self.save_file)
        self.file_menu.add_command(label='💾 Сохранить как…', command=self.save_file_as)
        self.file_menu.add_separator()
        self.file_menu.add_command(label='❌ Закрыть вкладку', command=self.close_current_tab)
        self.file_menu.add_command(label='🚪 Выход', command=self.on_exit)

        self.run_menu = tk.Menu(self.menubar, tearoff=0)
        self.run_menu.add_command(label='▶️ Запустить main.py (F5)', command=self.run_current)
        self.run_menu.add_command(label='⏹ Остановить (Shift+F5)', command=self.stop_process)
        self.run_menu.add_separator()
        self.run_menu.add_command(label='🧹 Очистить консоль', command=self.clear_console)

        self.tools_menu = tk.Menu(self.menubar, tearoff=0)
        self.tools_menu.add_command(label='↦ Сделать отступ', command=self.indent_selection)

        self.menubar.add_cascade(label='Файл', menu=self.file_menu)
        self.menubar.add_cascade(label='Запуск', menu=self.run_menu)
        self.menubar.add_cascade(label='Полезное', menu=self.tools_menu)
        self.menubar.add_command(label='⚙ Настройки', command=self._open_settings)
        self.config(menu=self.menubar)
        self._apply_menu_theme()

    def _bind_shortcuts(self) -> None:
        self.bind('<Control-n>', lambda _e: self.new_tab())
        self.bind('<Control-o>', lambda _e: self.open_file())
        self.bind('<Control-s>', lambda _e: self.save_file())
        self.bind('<Control-w>', lambda _e: self.close_current_tab())
        self.bind('<F5>', lambda _e: self.run_current())
        self.bind('<Shift-F5>', lambda _e: self.stop_process())
        self.protocol('WM_DELETE_WINDOW', self.on_exit)
        self.bind_all('<Control-n>', lambda _e: self.new_tab(), add=True)
        self.bind_all('<Control-N>', lambda _e: self.new_tab(), add=True)
        self.bind_all('<Control-o>', lambda _e: self.open_file(), add=True)
        self.bind_all('<Control-O>', lambda _e: self.open_file(), add=True)
        self.bind_all('<Control-s>', lambda _e: self.save_file(), add=True)
        self.bind_all('<Control-S>', lambda _e: self.save_file(), add=True)
        self.bind_all('<Control-w>', lambda _e: self.close_current_tab(), add=True)
        self.bind_all('<Control-W>', lambda _e: self.close_current_tab(), add=True)
        self.bind_all('<Control-a>', self._global_select_all, add=True)
        self.bind_all('<Control-A>', self._global_select_all, add=True)
        self.bind_all('<Control-c>', self._global_copy, add=True)
        self.bind_all('<Control-C>', self._global_copy, add=True)
        self.bind_all('<Control-v>', self._global_paste, add=True)
        self.bind_all('<Control-V>', self._global_paste, add=True)
        self.bind_all('<Control-x>', self._global_cut, add=True)
        self.bind_all('<Control-X>', self._global_cut, add=True)
        self.bind_all('<Control-z>', self._global_undo, add=True)
        self.bind_all('<Control-Z>', self._global_undo, add=True)
        self.bind_all('<Control-y>', self._global_redo, add=True)
        self.bind_all('<Control-Y>', self._global_redo, add=True)

    def _open_settings(self) -> None:
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_set()
            return

        self.settings_window = tk.Toplevel(self)
        self.settings_window.title('Настройки')
        self.settings_window.resizable(False, False)
        self.settings_window.configure(background=self.theme['app_bg'])

        frame = ttk.Frame(self.settings_window, padding=12)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text='Основные', font=('Consolas', 11, 'bold')).pack(anchor='w')

        ttk.Checkbutton(
            frame,
            text='Тёмная тема',
            variable=self.dark_mode,
            command=self._apply_theme,
        ).pack(anchor='w', pady=(6, 0))

        ttk.Label(frame, text='Сохранение перед запуском', font=('Consolas', 11, 'bold')).pack(
            anchor='w', pady=(12, 0)
        )

        ttk.Radiobutton(
            frame,
            text='Спрашивать и запомнить',
            variable=self.save_before_run_var,
            value='ask',
            command=self._apply_save_before_run_setting,
        ).pack(anchor='w', pady=(4, 0))
        ttk.Radiobutton(
            frame,
            text='Всегда сохранять',
            variable=self.save_before_run_var,
            value='always',
            command=self._apply_save_before_run_setting,
        ).pack(anchor='w')
        ttk.Radiobutton(
            frame,
            text='Никогда не сохранять (временный файл)',
            variable=self.save_before_run_var,
            value='never',
            command=self._apply_save_before_run_setting,
        ).pack(anchor='w')

        ttk.Button(frame, text='Закрыть', command=self.settings_window.destroy).pack(anchor='e', pady=(12, 0))

    def _apply_save_before_run_setting(self) -> None:
        mode = self.save_before_run_var.get()
        if mode == 'ask':
            self.save_on_run_preference = None
        elif mode == 'always':
            self.save_on_run_preference = True
        elif mode == 'never':
            self.save_on_run_preference = False

    def _is_running(self) -> bool:
        return self.process is not None or self.turtle_running

    def _update_run_controls(self) -> None:
        running = self._is_running()
        if running:
            self.run_button.configure(text='🔁 Перезапустить main.py (F5)')
            self.stop_button.state(['!disabled'])
        else:
            self.run_button.configure(text='▶️ Запустить main.py (F5)')
            self.stop_button.state(['disabled'])

    def _apply_menu_theme(self) -> None:
        if not hasattr(self, 'menubar'):
            return
        theme = self.theme
        for menu in (self.menubar, self.file_menu, self.run_menu, self.tools_menu):
            menu.configure(
                background=theme['menu_bg'],
                foreground=theme['menu_fg'],
                activebackground=theme['menu_active_bg'],
                activeforeground=theme['menu_active_fg'],
                borderwidth=0,
            )

    def _bind_input_shortcuts(self) -> None:
        self.bind_text_shortcuts(self.input_text)

    def bind_text_shortcuts(self, widget: tk.Text) -> None:
        widget.bind('<Control-a>', lambda _e, w=widget: self._select_all_widget(w))
        widget.bind('<Control-A>', lambda _e, w=widget: self._select_all_widget(w))
        widget.bind('<Control-c>', lambda _e, w=widget: self._clipboard_copy_widget(w))
        widget.bind('<Control-C>', lambda _e, w=widget: self._clipboard_copy_widget(w))
        widget.bind('<Control-x>', lambda _e, w=widget: self._clipboard_cut_widget(w))
        widget.bind('<Control-X>', lambda _e, w=widget: self._clipboard_cut_widget(w))
        widget.bind('<Control-v>', lambda _e, w=widget: self._clipboard_paste_widget(w))
        widget.bind('<Control-V>', lambda _e, w=widget: self._clipboard_paste_widget(w))
        widget.bind('<Control-z>', lambda _e, w=widget: self._undo_widget(w))
        widget.bind('<Control-Z>', lambda _e, w=widget: self._undo_widget(w))
        widget.bind('<Control-y>', lambda _e, w=widget: self._redo_widget(w))
        widget.bind('<Control-Y>', lambda _e, w=widget: self._redo_widget(w))
        widget.bind('<Control-KeyPress>', lambda e, w=widget: self._handle_control_key(w, e), add=True)

    def _global_select_all(self, _event=None) -> str | None:
        widget = self._resolve_text_target()
        if widget:
            return self._select_all_widget(widget)
        return None

    def _global_copy(self, _event=None) -> str | None:
        widget = self._resolve_text_target()
        if widget:
            return self._clipboard_copy_widget(widget)
        return None

    def _global_paste(self, _event=None) -> str | None:
        widget = self._resolve_text_target()
        if widget:
            return self._clipboard_paste_widget(widget)
        return None

    def _global_cut(self, _event=None) -> str | None:
        widget = self._resolve_text_target()
        if widget:
            return self._clipboard_cut_widget(widget)
        return None

    def _global_undo(self, _event=None) -> str | None:
        widget = self._resolve_text_target()
        if widget:
            return self._undo_widget(widget)
        return None

    def _global_redo(self, _event=None) -> str | None:
        widget = self._resolve_text_target()
        if widget:
            return self._redo_widget(widget)
        return None

    def _handle_control_key(self, widget: tk.Text, event: tk.Event) -> str | None:
        if not (event.state & 0x4):
            return None
        keycode_map = {
            65: self._select_all_widget,   # A
            67: self._clipboard_copy_widget,  # C
            86: self._clipboard_paste_widget,  # V
            88: self._clipboard_cut_widget,  # X
            90: self._undo_widget,  # Z
            89: self._redo_widget,  # Y
        }
        action = keycode_map.get(event.keycode)
        if action:
            return action(widget)
        return None

    def _resolve_text_target(self) -> tk.Text | None:
        widget = self.focus_get()
        if isinstance(widget, tk.Text):
            return widget
        tab = self.get_current_tab()
        if tab:
            return tab.text
        return None

    def indent_selection(self) -> None:
        tab = self.get_current_tab()
        if not tab:
            return
        self._indent_selection(tab.text)

    def _indent_or_tab(self, widget: tk.Text) -> str:
        if widget.tag_ranges('sel'):
            return self._indent_selection(widget)
        widget.insert('insert', '    ')
        return 'break'

    def _indent_selection(self, widget: tk.Text) -> str:
        try:
            start = widget.index('sel.first')
            end = widget.index('sel.last')
        except tk.TclError:
            widget.insert('insert', '    ')
            return 'break'
        start_line = int(start.split('.')[0])
        end_line = int(end.split('.')[0])
        if end.endswith('.0') and end_line > start_line:
            end_line -= 1
        widget.edit_separator()
        for line in range(start_line, end_line + 1):
            widget.insert(f'{line}.0', '    ')
        widget.tag_remove('sel', '1.0', 'end')
        widget.tag_add('sel', f'{start_line}.0', f'{end_line}.end')
        return 'break'

    def _on_input_focus_in(self, _event=None) -> None:
        self.input_text.configure(background=self.theme['input_bg_focus'])

    def _on_input_focus_out(self, _event=None) -> None:
        self.input_text.configure(background=self.theme['input_bg'])

    def _update_input_state(self) -> None:
        self.input_text.configure(state='normal')

    def _focus_input(self) -> None:
        self.input_text.focus_set()
        self.input_text.configure(background=self.theme['input_bg_focus'])

    def _pulse_input_focus(self) -> None:
        self._focus_input()
        self.input_text.configure(
            highlightbackground=self.theme['accent_dark'],
            highlightcolor=self.theme['accent_dark'],
        )
        self.after(
            350,
            lambda: self.input_text.configure(
                highlightbackground=self.theme['accent'],
                highlightcolor=self.theme['accent'],
            ),
        )

    def _insert_input_newline(self, _event=None) -> str:
        self.input_text.insert('insert', '\n')
        return 'break'

    def _append_input_echo(self, text: str) -> None:
        lines = text.split('\n')
        items: list[tuple[str, str]] = []
        if not lines:
            items.append(('stdin', INPUT_PREFIX))
            items.append(('stdout', '\n'))
        else:
            for idx, line in enumerate(lines):
                items.append(('stdin', INPUT_PREFIX))
                items.append(('stdout', line))
                if idx < len(lines) - 1:
                    items.append(('stdout', '\n'))
            items.append(('stdout', '\n'))
        self._append_output_batch(items)

    def _send_console_input(self, _event=None) -> str:
        if _event is not None and (_event.state & 0x4):
            return 'break'

        text = self.input_text.get('1.0', 'end-1c')
        self.input_text.delete('1.0', 'end')

        if self.process and self.process.stdin:
            self._append_input_echo(text)
            try:
                payload = text
                if not payload.endswith('\n'):
                    payload += '\n'
                self.process.stdin.write(payload)
                self.process.stdin.flush()
            except Exception as exc:
                self._append_output(f'ОШИБКА ВВОДА: {exc}\n', tag='status')
        else:
            if text.strip():
                self._append_input_echo(text)
            self._append_output('Нет запущенного процесса.\n', tag='status')
        return 'break'

    def _select_all_widget(self, widget: tk.Text) -> str:
        widget.tag_add('sel', '1.0', 'end')
        return 'break'

    def _clipboard_copy_widget(self, widget: tk.Text) -> str:
        text = self._get_selection(widget)
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
        return 'break'

    def _clipboard_cut_widget(self, widget: tk.Text) -> str:
        text = self._get_selection(widget)
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._delete_selection(widget)
        return 'break'

    def _clipboard_paste_widget(self, widget: tk.Text) -> str:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return 'break'
        self._replace_selection(widget, text)
        return 'break'

    def _undo_widget(self, widget: tk.Text) -> str:
        try:
            widget.edit_undo()
        except tk.TclError:
            pass
        return 'break'

    def _redo_widget(self, widget: tk.Text) -> str:
        try:
            widget.edit_redo()
        except tk.TclError:
            pass
        return 'break'

    def _console_copy(self, _event=None) -> str:
        self._clipboard_copy_widget(self.console)
        return 'break'

    def _get_selection(self, widget: tk.Text) -> str:
        try:
            return widget.get('sel.first', 'sel.last')
        except tk.TclError:
            return ''

    def _delete_selection(self, widget: tk.Text) -> None:
        try:
            widget.delete('sel.first', 'sel.last')
        except tk.TclError:
            pass

    def _replace_selection(self, widget: tk.Text, text: str) -> None:
        try:
            widget.delete('sel.first', 'sel.last')
        except tk.TclError:
            pass
        widget.insert('insert', text)

    def new_tab(self) -> None:
        tab = EditorTab(self)
        tab.virtual_name = self._next_virtual_name()
        self.notebook.add(tab.frame, text=tab.virtual_name)
        self.tabs_by_frame[str(tab.frame)] = tab
        self.notebook.select(tab.frame)
        tab.text.focus_set()
        if tab.virtual_name == 'main.py':
            self.main_tab = tab

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            filetypes=[('Python', '*.py'), ('All files', '*.*')],
        )
        if not path:
            return
        file_path = Path(path)
        try:
            content = read_text_file(file_path)
        except Exception as exc:
            messagebox.showerror('Не удалось открыть', str(exc))
            return
        main_tab = self.main_tab or self._ensure_main_tab()
        if main_tab and not main_tab.path and not main_tab.modified and not main_tab.get_content().strip():
            main_tab.path = file_path
            main_tab.set_content(content)
            self.notebook.select(main_tab.frame)
            main_tab.text.focus_set()
            self.update_tab_title(main_tab)
            return
        tab = EditorTab(self, file_path)
        tab.set_content(content)
        self.notebook.add(tab.frame, text=file_path.name)
        self.tabs_by_frame[str(tab.frame)] = tab
        self.notebook.select(tab.frame)
        tab.text.focus_set()

    def save_file(self) -> bool:
        tab = self.get_current_tab()
        if not tab:
            return False
        if tab.path is None:
            return self.save_file_as()
        return self._write_file(tab.path, tab)

    def save_file_as(self) -> bool:
        tab = self.get_current_tab()
        if not tab:
            return False
        path = filedialog.asksaveasfilename(
            defaultextension='.py',
            filetypes=[('Python', '*.py'), ('All files', '*.*')],
        )
        if not path:
            return False
        tab.path = Path(path)
        return self._write_file(tab.path, tab)

    def save_archive(self) -> None:
        if not self.tabs_by_frame:
            messagebox.showinfo('Архив', 'Нет открытых модулей для архивации.')
            return

        target = filedialog.asksaveasfilename(
            defaultextension='.zip',
            filetypes=[('ZIP', '*.zip')],
        )
        if not target:
            return

        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        staging = RUNTIME_DIR / 'archive'
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)

        used: set[str] = set()

        def unique_name(base: str) -> str:
            stem, suffix = os.path.splitext(base)
            if not suffix:
                suffix = '.py'
            candidate = f'{stem}{suffix}'
            index = 2
            while candidate in used:
                candidate = f'{stem}_{index}{suffix}'
                index += 1
            used.add(candidate)
            return candidate

        for tab in self.tabs_by_frame.values():
            name = unique_name(self._runtime_name_for_tab(tab))
            dest = staging / name
            dest.write_text(tab.get_content(), encoding='utf-8')

        try:
            if os.name == 'nt':
                src = str(staging / '*')
                ps_src = src.replace("'", "''")
                ps_dst = target.replace("'", "''")
                cmd = [
                    'powershell',
                    '-NoProfile',
                    '-Command',
                    f"Compress-Archive -Path '{ps_src}' -DestinationPath '{ps_dst}' -Force",
                ]
            else:
                cmd = ['tar', '-czf', target, '-C', str(staging), '.']

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or 'Не удалось создать архив.')
        except FileNotFoundError:
            messagebox.showerror('Архив', 'Системный архиватор не найден.')
            return
        except Exception as exc:
            messagebox.showerror('Архив', str(exc))
            return
        finally:
            shutil.rmtree(staging, ignore_errors=True)

        messagebox.showinfo('Архив', f'Архив сохранён: {target}')

    def _write_file(self, path: Path, tab: EditorTab) -> bool:
        try:
            path.write_text(tab.get_content(), encoding='utf-8')
        except Exception as exc:
            messagebox.showerror('Не удалось сохранить', str(exc))
            return False
        if tab is not self.main_tab:
            tab.virtual_name = None
        tab.modified = False
        tab.text.edit_modified(False)
        self.update_tab_title(tab)
        return True

    def update_tab_title(self, tab: EditorTab) -> None:
        if tab is self.main_tab:
            title = 'main.py'
        else:
            title = tab.path.name if tab.path else (tab.virtual_name or 'Без имени')
        if tab.modified:
            title = f'*{title}'
        self.notebook.tab(tab.frame, text=title)

    def _next_virtual_name(self) -> str:
        if not self._main_created:
            self._main_created = True
            return 'main.py'
        used = set()
        for tab in self.tabs_by_frame.values():
            name = tab.path.name if tab.path else (tab.virtual_name or '')
            lower = name.lower()
            if lower.startswith('module') and lower.endswith('.py'):
                digits = lower[6:-3]
                if digits.isdigit():
                    used.add(int(digits))
        index = 1
        while index in used:
            index += 1
        return f'module{index}.py'

    def _ensure_main_tab(self) -> EditorTab:
        if self.main_tab:
            return self.main_tab
        tab = EditorTab(self)
        tab.virtual_name = 'main.py'
        self.notebook.add(tab.frame, text='main.py')
        self.tabs_by_frame[str(tab.frame)] = tab
        self.notebook.select(tab.frame)
        tab.text.focus_set()
        self.main_tab = tab
        self._main_created = True
        return tab

    def get_current_tab(self) -> EditorTab | None:
        frame_id = self.notebook.select()
        if not frame_id:
            return None
        return self.tabs_by_frame.get(frame_id)

    def close_current_tab(self) -> None:
        tab = self.get_current_tab()
        if not tab:
            return
        if tab is self.main_tab:
            messagebox.showinfo('Main.py', 'Нельзя закрыть main.py. Он всегда должен быть в проекте.')
            return
        if not self._confirm_discard(tab):
            return
        self.notebook.forget(tab.frame)
        self.tabs_by_frame.pop(str(tab.frame), None)
        if not self.tabs_by_frame:
            self.new_tab()

    def _on_tab_changed(self, _event=None) -> None:
        self._focus_editor()

    def _focus_editor(self) -> None:
        tab = self.get_current_tab()
        if tab:
            tab.text.focus_set()

    def _confirm_discard(self, tab: EditorTab) -> bool:
        if not tab.modified:
            return True
        response = messagebox.askyesnocancel('Несохранённые изменения', 'Сохранить изменения перед закрытием?')
        if response is None:
            return False
        if response:
            return self._save_or_cancel(tab)
        return True

    def _save_or_cancel(self, tab: EditorTab) -> bool:
        if tab.path is None:
            path = filedialog.asksaveasfilename(
                defaultextension='.py',
                filetypes=[('Python', '*.py'), ('All files', '*.*')],
            )
            if not path:
                return False
            tab.path = Path(path)
        return self._write_file(tab.path, tab)

    def on_exit(self) -> None:
        self._closing = True
        self.turtle_abort = True
        for tab in list(self.tabs_by_frame.values()):
            if not self._confirm_discard(tab):
                return
        self.stop_process()
        self.destroy()

    def run_current(self) -> None:
        tab = self.main_tab or self.get_current_tab()
        if tab is None or tab is not self.main_tab:
            tab = self._ensure_main_tab()
        if not tab:
            return
        if self.process:
            if not messagebox.askyesno('Процесс уже запущен', 'Остановить текущий процесс и запустить снова?'):
                return
            self.stop_process()

        script_path = self._prepare_run_path(tab)
        if not script_path:
            return

        code = tab.get_content()
        if self._needs_turtle(tab, script_path):
            self._run_turtle_code(code, script_path)
            return

        python_exe = get_python_executable()
        if not python_exe:
            messagebox.showerror(
                'Portable Python не найден',
                'Portable Python не найден в папке python.\n'
                'Запусти скрипт запуска в этой папке, чтобы использовать встроенный Python.',
            )
            return

        self.clear_console()
        self._append_output(f'Запуск: {script_path}\n', tag='status')
        self._run_in_console(python_exe, script_path)
        self._focus_input()
        self._update_run_controls()

    def _run_in_console(self, python_exe: str, script_path: Path) -> None:
        try:
            self.process = subprocess.Popen(
                [python_exe, '-u', str(script_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(script_path.parent),
            )
        except Exception as exc:
            self._append_output(f'Ошибка запуска: {exc}\n', tag='status')
            self.process = None
            return

        threading.Thread(target=self._read_stream, args=(self.process.stdout, 'stdout'), daemon=True).start()
        threading.Thread(target=self._read_stream, args=(self.process.stderr, 'stderr'), daemon=True).start()
        threading.Thread(target=self._watch_process, daemon=True).start()
        self._update_run_controls()

    def _code_uses_turtle(self, code: str) -> bool:
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
        except Exception:
            return False
        for idx, (tok_type, tok_str, *_rest) in enumerate(tokens):
            if tok_type == tokenize.NAME and tok_str == 'import':
                j = idx + 1
                while j < len(tokens):
                    t_type, t_str, *_ = tokens[j]
                    if t_type in (tokenize.NEWLINE, tokenize.NL):
                        break
                    if t_type == tokenize.NAME and t_str == 'turtle':
                        return True
                    j += 1
            if tok_type == tokenize.NAME and tok_str == 'from':
                j = idx + 1
                while j < len(tokens):
                    t_type, t_str, *_ = tokens[j]
                    if t_type in (tokenize.NEWLINE, tokenize.NL):
                        break
                    if t_type == tokenize.NAME:
                        return t_str == 'turtle'
                    j += 1
        return False

    def _collect_imports(self, code: str) -> set[str]:
        imports: set[str] = set()
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
        except Exception:
            return imports
        idx = 0
        while idx < len(tokens):
            tok_type, tok_str, *_ = tokens[idx]
            if tok_type == tokenize.NAME and tok_str == 'import':
                idx += 1
                while idx < len(tokens):
                    t_type, t_str, *_ = tokens[idx]
                    if t_type in (tokenize.NEWLINE, tokenize.NL):
                        break
                    if t_type == tokenize.NAME:
                        imports.add(t_str.split('.')[0])
                    idx += 1
            elif tok_type == tokenize.NAME and tok_str == 'from':
                idx += 1
                while idx < len(tokens):
                    t_type, t_str, *_ = tokens[idx]
                    if t_type in (tokenize.NEWLINE, tokenize.NL):
                        break
                    if t_type == tokenize.NAME:
                        imports.add(t_str.split('.')[0])
                        break
                    idx += 1
            idx += 1
        return imports

    def _module_name_for_tab(self, tab: EditorTab) -> str:
        if tab.path:
            return tab.path.stem
        name = tab.virtual_name or ''
        if name.lower().endswith('.py'):
            return name[:-3]
        return name

    def _load_module_source(self, module_name: str, script_path: Path | None) -> str | None:
        for other in self.tabs_by_frame.values():
            mod_name = self._module_name_for_tab(other)
            if mod_name == module_name:
                return other.get_content()
        if script_path:
            candidate = script_path.parent / f'{module_name}.py'
            if candidate.exists():
                try:
                    return read_text_file(candidate)
                except Exception:
                    return None
        return None

    def _needs_turtle(self, tab: EditorTab, script_path: Path | None) -> bool:
        root_code = tab.get_content()
        if self._code_uses_turtle(root_code):
            return True
        pending = list(self._collect_imports(root_code))
        seen: set[str] = set()
        while pending:
            module_name = pending.pop()
            if module_name in seen:
                continue
            seen.add(module_name)
            source = self._load_module_source(module_name, script_path)
            if not source:
                continue
            if self._code_uses_turtle(source):
                return True
            pending.extend(self._collect_imports(source) - seen)
        return False

    def _show_turtle_panel(self, show: bool) -> None:
        if show and not self.turtle_visible:
            self.editor_paned.add(self.turtle_frame, weight=2)
            self.turtle_visible = True
        elif not show and self.turtle_visible:
            self.editor_paned.forget(self.turtle_frame)
            self.turtle_visible = False

    def _prepare_turtle_screen(self) -> None:
        import turtle

        self._show_turtle_panel(True)
        self.turtle_canvas.focus_set()

        if not self._turtle_initialized or not self.turtle_screen:
            self.turtle_canvas.delete('all')
            turtle.Turtle._screen = None
            turtle.Turtle._pen = None
            self.turtle_screen = turtle.TurtleScreen(self.turtle_canvas)
            self._turtle_initialized = True
        else:
            try:
                self.turtle_screen.clear()
            except Exception:
                self.turtle_canvas.delete('all')

        self.update_idletasks()
        self._turtle_custom_coords = False
        self._turtle_setworld = self.turtle_screen.setworldcoordinates
        self._sync_turtle_world()
        self.turtle_screen.bgcolor(self.theme['panel_bg'])
        self.turtle_screen._delayvalue = 10
        try:
            self.turtle_screen.listen()
        except Exception:
            pass

        turtle.Turtle._screen = self.turtle_screen
        turtle.Turtle._pen = None
        turtle._screen = self.turtle_screen
        turtle._pen = None
        turtle.Screen = lambda: self.turtle_screen
        turtle.getscreen = lambda: self.turtle_screen

        turtle._getscreen = lambda: self.turtle_screen
        turtle._getcanvas = lambda: self.turtle_canvas

        for name in ('bye', 'exitonclick', 'done', 'mainloop'):
            setattr(turtle, name, lambda *args, **kwargs: None)
        self.turtle_screen.bye = lambda *args, **kwargs: None
        self.turtle_screen.mainloop = lambda *args, **kwargs: None
        self._wrap_turtle_setworld()

    def _wrap_turtle_setworld(self) -> None:
        if not self.turtle_screen or not self._turtle_setworld:
            return
        original = self._turtle_setworld

        def wrapped(*args, **kwargs):
            self._turtle_custom_coords = True
            return original(*args, **kwargs)

        self.turtle_screen.setworldcoordinates = wrapped

    def _sync_turtle_world(self) -> None:
        if not self.turtle_screen or self._turtle_custom_coords:
            return
        width = self.turtle_canvas.winfo_width()
        height = self.turtle_canvas.winfo_height()
        if width > 2 and height > 2 and self._turtle_setworld:
            try:
                self._turtle_setworld(-width / 2, -height / 2, width / 2, height / 2)
            except Exception:
                pass

    def _on_turtle_canvas_resize(self, _event=None) -> None:
        self._sync_turtle_world()

    def _run_turtle_code(self, code: str, script_path: Path) -> None:
        self.clear_console()
        self._append_output(f'Запуск (turtle): {script_path}\n', tag='status')
        self._prepare_turtle_screen()
        self.turtle_running = True
        self.turtle_abort = False
        self._update_run_controls()

        def _execute() -> None:
            globals_dict = {
                '__name__': '__main__',
                '__file__': str(script_path),
            }
            prev_trace = sys.gettrace()
            prev_cwd = os.getcwd()
            script_dir = str(script_path.parent)
            path_inserted = False
            last_tick = time.perf_counter()

            def tracer(_frame, event, _arg):
                nonlocal last_tick
                if self.turtle_abort or self._closing:
                    raise SystemExit
                if event == 'line':
                    now = time.perf_counter()
                    if now - last_tick >= TURTLE_UI_PUMP_INTERVAL:
                        last_tick = now
                        try:
                            if self.turtle_screen:
                                self.turtle_screen.update()
                            self.update()
                        except tk.TclError:
                            return None
                return tracer

            sys.settrace(tracer)
            try:
                if script_dir and script_dir not in sys.path:
                    sys.path.insert(0, script_dir)
                    path_inserted = True
                try:
                    os.chdir(script_dir)
                except OSError:
                    pass
                exec(compile(code, str(script_path), 'exec'), globals_dict)
            except SystemExit:
                if not self._closing:
                    self._append_output('Остановлено\n', tag='status')
            except Exception:
                self._append_output(traceback.format_exc(), tag='stderr')
            finally:
                sys.settrace(prev_trace)
                self.turtle_running = False
                self._update_run_controls()
                if self.turtle_screen:
                    try:
                        self.turtle_screen.update()
                    except Exception:
                        pass
                if path_inserted:
                    try:
                        sys.path.remove(script_dir)
                    except ValueError:
                        pass
                try:
                    os.chdir(prev_cwd)
                except OSError:
                    pass
                self._append_output('Готово.\n', tag='status')

        self.after(10, _execute)

    def _prepare_run_path(self, tab: EditorTab) -> Path | None:
        if tab.modified:
            mode = self.save_before_run_var.get()
            if mode == 'always':
                self.save_on_run_preference = True
            elif mode == 'never':
                self.save_on_run_preference = False

            if self.save_on_run_preference is None:
                response = messagebox.askyesnocancel(
                    'Несохранённые изменения',
                    'Сохранить перед запуском? (выбор будет запомнен)',
                )
                if response is None:
                    return None
                self.save_on_run_preference = bool(response)
                self.save_before_run_var.set('always' if response else 'never')

            if self.save_on_run_preference:
                if not self.save_file():
                    return None
            else:
                return self._write_temp_script(tab)
        if tab.path is None:
            return self._write_temp_script(tab)
        return tab.path

    def _runtime_name_for_tab(self, tab: EditorTab) -> str:
        if tab is self.main_tab:
            name = 'main.py'
        elif tab.path:
            name = tab.path.name
        else:
            name = tab.virtual_name or 'module'
        if not name.lower().endswith('.py'):
            name = f'{name}.py'
        return name

    def _build_runtime_files(self, primary_tab: EditorTab) -> Path:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        used: set[str] = set()

        def unique_name(base: str) -> str:
            stem, suffix = os.path.splitext(base)
            if not suffix:
                suffix = '.py'
            candidate = f'{stem}{suffix}'
            index = 2
            while candidate in used:
                candidate = f'{stem}_{index}{suffix}'
                index += 1
            used.add(candidate)
            return candidate

        primary_name = unique_name(self._runtime_name_for_tab(primary_tab))
        primary_path = RUNTIME_DIR / primary_name
        primary_path.write_text(primary_tab.get_content(), encoding='utf-8')

        for tab in self.tabs_by_frame.values():
            if tab is primary_tab:
                continue
            name = unique_name(self._runtime_name_for_tab(tab))
            (RUNTIME_DIR / name).write_text(tab.get_content(), encoding='utf-8')

        return primary_path

    def _write_temp_script(self, tab: EditorTab) -> Path:
        return self._build_runtime_files(tab)

    def _read_stream(self, stream, tag: str) -> None:
        if stream is None:
            return
        while True:
            chunk = stream.read(1)
            if chunk == '':
                break
            self.output_queue.put((tag, chunk))
        stream.close()

    def _watch_process(self) -> None:
        if not self.process:
            return
        code = self.process.wait()
        self.output_queue.put(('status', f'\nПроцесс завершён, код: {code}\n'))
        self.output_queue.put(('done', None))

    def _poll_output(self) -> None:
        items: list[tuple[str, str]] = []
        try:
            while True:
                tag, text = self.output_queue.get_nowait()
                if tag == 'done':
                    self.process = None
                    self._update_run_controls()
                else:
                    items.append((tag, text or ''))
        except queue.Empty:
            pass
        if items:
            self._append_output_batch(items)
        self.after(POLL_DELAY_MS, self._poll_output)

    def _append_output_batch(self, items: list[tuple[str, str]]) -> None:
        self.console.configure(state='normal')
        combined = ''
        for tag, text in items:
            self.console.insert('end', text, tag)
            combined += text
        self.console.see('end')
        self.console.configure(state='disabled')
        if self.process and combined:
            self._maybe_focus_input_on_output(combined)

    def _append_output(self, text: str, tag: str = 'stdout') -> None:
        self._append_output_batch([(tag, text)])

    def _maybe_focus_input_on_output(self, text: str) -> None:
        if not text.strip():
            return
        if not text.endswith('\n'):
            self._pulse_input_focus()

    def _pulse_input_focus(self) -> None:
        self._focus_input()

    def clear_console(self) -> None:
        self.console.configure(state='normal')
        self.console.delete('1.0', 'end')
        self.console.configure(state='disabled')

    def stop_process(self) -> None:
        if self.turtle_running:
            self.turtle_abort = True
            return
        if not self.process:
            self._update_run_controls()
            return
        try:
            self.process.terminate()
            self.process.wait(timeout=1.5)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        self.process = None
        self._append_output('Остановлено\n', tag='status')
        self._update_run_controls()


if __name__ == '__main__':
    app = PortableIDE()
    app.mainloop()
