# Техническая документация

## Структура проекта
```
Python-Portable - Codex/
  MSHP-IDE-Windows/
    app/ide.py
    python/              # portable Python для Windows (минимизированный)
    .runtime/
    МШПаха.Оффлайн.bat
  MSHP-IDE-macOS/
    app/ide.py
    python/
      x86_64/            # Intel
      aarch64/           # Apple Silicon
    .runtime/
    МШПаха.Оффлайн.sh
  MSHP-IDE-Linux/
    app/ide.py
    python/
      x86_64/            # Intel/AMD
      aarch64/           # ARM
    .runtime/
    МШПаха.Оффлайн.sh
  docs/
```

## Запуск и поиск Python
- Используется **portable‑Python** в `python/`.
- Можно указать переменную окружения `PYTHON_PORTABLE`.
- Поиск выполняется функцией `find_python_in_dir`:
  - Windows: ищет `python.exe`.
  - macOS/Linux: ищет `python3` или `python`.
- В macOS/Linux `МШПаха.Оффлайн.sh` выбирает папку по архитектуре (`x86_64` или `aarch64`)
  и выставляет `PYTHONHOME`, `TCL_LIBRARY`, `TK_LIBRARY`.

## Архитектура IDE
- UI построен на `tkinter` (`ttk` + `Text`).
- Основной файл: `app/ide.py`.
- Вкладки реализованы через `ttk.Notebook`.
- Подсветка синтаксиса: `tokenize` + теги `Text`.
- Нумерация строк: отдельный `Canvas` слева от редактора.

## Запуск кода
- При запуске создаётся subprocess:
  - `python -u <script>`
  - stdin/stdout/stderr подключены пайпами.
- Вывод читается отдельными потоками и складируется в очередь.
- UI опрашивает очередь через `after()` и дописывает в консоль.

## Ввод
- Поле ввода — отдельный `Text` между редактором и консолью.
- `Enter` отправляет текст в stdin процесса, `Ctrl+Enter` вставляет перенос.
- Каждый ввод отображается в консоли с префиксом `>`.
- В turtle‑режиме `input()` заменяется на чтение из GUI‑очереди (`input_queue`).

## Turtle‑режим
- Если код содержит `import turtle` или `from turtle import ...`,
  запуск идёт **внутри процесса IDE**, без subprocess.
- Справа появляется панель с `Canvas`, на котором создаётся `turtle.TurtleScreen`.
- `turtle.done/exitonclick/mainloop/bye` переопределяются в no‑op.
- `builtins.input` и `globals()['input']` подменяются, чтобы ввод работал в turtle‑режиме.
- `turtle._getscreen` и `turtle._getcanvas` указывают на встроенный `Canvas`.
- Координаты экрана синхронизируются с размером встроенной панели (центр в (0, 0)).
- Рисунок остаётся видимым после завершения кода.

## Темы
- Две темы: `light` и `dark` в словаре `THEMES`.
- Переключатель темы вызывает `_apply_theme()`,
  который перекрашивает все элементы UI.

## Минимизация размера (Windows/macOS/Linux)
Для уменьшения веса удалены компоненты, не влияющие на работу IDE:
- `site-packages`, `ensurepip`, `venv`, `idlelib`, `turtledemo`, `pydoc_data`
- `Scripts`, `include`, `libs`
- `notebooks/`, `scripts/` и дополнительные `.exe` WinPython
- все `__pycache__`

Эти изменения **не влияют** на запуск IDE и стандартной библиотеки.
Если нужны сторонние библиотеки, положи их в `python/Lib/site-packages`.

## Ограничения и риски
- В IDE нет полноценного терминала — только stdin/stdout.
- Встроенного `pip` нет (удалён ради веса).
- Turtle запускается в том же процессе: бесконечные циклы в коде блокируют UI.

## Точки расширения
- Можно добавить установщик библиотек (локальный `pip`) при необходимости.
- Можно добавить кнопку очистки turtle‑панели.
