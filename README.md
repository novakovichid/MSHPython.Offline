# Python-Portable - Codex

Проект разделён по ОС. Внутри каждого каталога — своя portable‑версия и скрипт запуска.
Пользовательская и техническая документация — в `docs/`.

## Структура
```
Python-Portable - Codex/
  MSHP-IDE-Windows/
  MSHP-IDE-macOS/
  MSHP-IDE-Linux/
```

## Windows
Перейди в `MSHP-IDE-Windows/` и запусти `run_ide.bat`.

## macOS / Linux
Перейди в `MSHP-IDE-macOS/` или `MSHP-IDE-Linux/` и запусти `./run_ide.sh`
(понадобится `chmod +x run_ide.sh`).
Внутри лежат два portable‑сборочных варианта: `python/x86_64` и `python/aarch64`.

## Примечание
IDE оффлайн и ничего не скачивает без твоей команды.
Если в коде есть `import turtle`, справа появится встроенная панель черепашки (без всплывающих окон), а `input()` работает через поле ввода IDE.
