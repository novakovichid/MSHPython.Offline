"""Логика оркестрации перезапуска: guard двойного клика, сброс turtle_abort,
on_exit при отмене закрытия."""
import sys
import importlib.util
from pathlib import Path

APP = Path(__file__).resolve().parent / 'MSHP-IDE-Windows' / 'app' / 'ide.py'
spec = importlib.util.spec_from_file_location('ide_logic', APP)
ide = importlib.util.module_from_spec(spec)
sys.modules['ide_logic'] = ide
spec.loader.exec_module(ide)
print('import ide.py: OK')

TAB = object()
P = ide.PortableIDE


class Fake:
    def __init__(self, running):
        self._running = running
        self._closing = False
        self._restart_pending = False
        self.turtle_abort = False
        self.step_abort = False
        self.step_mode = False
        self.main_tab = TAB
        self.events = []
        self._budget = 200
    # зависимости
    def get_current_tab(self): return TAB
    def _ensure_main_tab(self): return TAB
    def _is_running(self): return self._running
    def _update_run_controls(self): self.events.append('controls')
    def _show_step_controls(self, x): pass
    def stop_process(self): self.events.append('stop')
    def _confirm_discard(self, tab): return self._confirm
    def _clear_temp_session(self): self.events.append('clear_temp')
    def destroy(self): self.events.append('destroy')
    def after(self, ms, cb):
        self.events.append(f'after{ms}')
        self._budget -= 1
        assert self._budget > 0, 'after-loop не сошёлся'
        cb()
    # _start_run заменяем: фиксируем факт и НЕ запускаем реальный пайплайн
    def _start_run(self, tab, step_mode):
        self.events.append('start')
        self.started_step = step_mode
    # настоящие тестируемые методы
    run_current = P.run_current
    _schedule_restart = P._schedule_restart
    on_exit = P.on_exit


# --- 1: guard — пока _restart_pending, повторный клик игнорируется ---
f = Fake(running=True)
# имитируем, что остановка асинхронная (turtle): _is_running остаётся True,
# пока не «завершится». Сделаем так, чтобы после первого after стало False.
calls = {'n': 0}
def stop_async(self=f):
    self.events.append('stop')
f.stop_process = stop_async
orig_after = f.after
def after_flip(ms, cb):
    f.events.append(f'after{ms}')
    f._running = False           # старый запуск завершился
    cb()
f.after = after_flip

f.run_current()                  # первый клик: ставит pending, stop, schedule
assert f._restart_pending in (False,), 'после полного цикла pending должен сняться'
assert f.events.count('start') == 1, f'ожидался один старт: {f.events}'
print('1 guard/основной цикл: OK ->', f.events)

# --- 2: повторный клик во время pending — no-op ---
f2 = Fake(running=True)
f2.stop_process = lambda: f2.events.append('stop')
f2.after = lambda ms, cb: f2.events.append(f'after{ms}')   # НЕ выполняем cb (висим)
f2.run_current()                 # pending=True, ушли в ожидание (after не дёрнул cb)
assert f2._restart_pending is True, 'pending должен стоять'
before = list(f2.events)
f2.run_current()                 # повторный клик
f2.run_current()                 # ещё раз
assert f2.events == before, f'повторные клики не должны ничего делать: {f2.events}'
assert f2.events.count('stop') == 1, 'stop вызван более одного раза'
print('2 повторные клики при pending — no-op: OK ->', f2.events)

# --- 3: _start_run сбрасывает turtle_abort (до ветки запуска) ---
fake_tab = type('T', (), {'get_content': lambda self: 'code'})()
f3b = Fake(running=False)
f3b.turtle_abort = True
f3b.step_abort = True
f3b._prepare_run_context = lambda tab: (Path('x.py'), None)   # валидный контекст
f3b._needs_turtle = lambda tab, sp: True                       # уходим в turtle-ветку
f3b._run_turtle_code = lambda *a: f3b.events.append('turtle')  # без реального запуска
f3b.step_event = type('E', (), {'clear': lambda self: None})()
f3b._start_run = P._start_run.__get__(f3b)
f3b._start_run(fake_tab, False)
assert f3b.turtle_abort is False, 'turtle_abort не сброшен в _start_run'
assert f3b.step_abort is False, 'step_abort не сброшен в _start_run'
assert 'turtle' in f3b.events, 'не дошли до ветки запуска'
print('3 _start_run сбрасывает turtle_abort/step_abort: OK')

# --- 4: on_exit при отмене закрытия восстанавливает флаги ---
f4 = Fake(running=False)
f4._confirm = False              # пользователь жмёт «Отмена»
f4.tabs_by_frame = {'a': TAB}
f4.on_exit()
assert f4._closing is False, '_closing должен быть восстановлен'
assert f4.turtle_abort is False and f4.step_abort is False, 'abort-флаги не сброшены'
assert 'destroy' not in f4.events, 'окно не должно закрываться при отмене'
print('4 on_exit при отмене восстанавливает флаги: OK')

# --- 5: on_exit при подтверждении закрывает ---
f5 = Fake(running=False)
f5._confirm = True
f5.tabs_by_frame = {'a': TAB}
f5.on_exit()
assert f5._closing is True and 'destroy' in f5.events, 'закрытие не выполнено'
print('5 on_exit при подтверждении закрывает: OK')

print('\nALL ASSERTIONS PASSED')
