"""Воспроизведение гонки «перезапуск subprocess»: stale 'done' старого
процесса не должен обнулять новый процесс. Тест на реальных потоках/очереди
и настоящих подпроцессах портативного Python."""
import sys
import time
import queue
import threading
import subprocess
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'MSHP-IDE-Windows' / 'app' / 'ide.py'
PY = ROOT / 'MSHP-IDE-Windows' / 'python' / 'WPy64-31500' / 'python' / 'python.exe'

spec = importlib.util.spec_from_file_location('ide_race', APP)
ide = importlib.util.module_from_spec(spec)
sys.modules['ide_race'] = ide
spec.loader.exec_module(ide)
print('import ide.py: OK')


class Harness:
    """Минимум, чтобы крутить реальные _read_stream/_watch_process/_poll_output."""
    def __init__(self):
        self.output_queue = queue.Queue()
        self.process = None
        self.appended = []          # всё, что ушло бы в консоль
        self.controls_updates = 0
        self._after_calls = []
        self._closing = False
        self._restart_pending = False
        self._silenced_procs = set()
    def _update_run_controls(self):
        self.controls_updates += 1
    def _append_output_batch(self, items):
        self.appended.extend(items)
    def after(self, ms, cb):
        # не зацикливаем реальный poll — просто фиксируем, что он перепланирован
        self._after_calls.append(ms)

    _read_stream = ide.PortableIDE._read_stream
    _watch_process = ide.PortableIDE._watch_process
    _poll_output = ide.PortableIDE._poll_output

    def drain_once(self):
        self._poll_output()   # один проход разбора очереди


def spawn(code):
    return subprocess.Popen(
        [str(PY), '-u', '-c', code],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )


def wait_queue_has(h, pred, timeout=10):
    end = time.perf_counter() + timeout
    while time.perf_counter() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


# ====== СЦЕНАРИЙ ГОНКИ (как в баг-репорте) ======
h = Harness()

# P1 — «старая сессия», ждёт ввод (аналог while x: x=input())
p1 = spawn('import sys\nsys.stdout.write("p1-started\\n"); sys.stdout.flush()\nsys.stdin.readline()')
h.process = p1
threading.Thread(target=h._read_stream, args=(p1, p1.stdout, 'stdout'), daemon=True).start()
threading.Thread(target=h._read_stream, args=(p1, p1.stderr, 'stderr'), daemon=True).start()
threading.Thread(target=h._watch_process, args=(p1,), daemon=True).start()

# дождались стартового вывода p1
assert wait_queue_has(h, lambda: not h.output_queue.empty()), 'p1 не дал вывода'

# --- пользователь жмёт «Перезапустить»: имитируем stop_process для subprocess ---
p1.terminate()
p1.wait(timeout=5)
h.process = None                       # как делает stop_process

# наблюдатель p1 положит ('done', None, p1) — ждём появления 'done' в очереди
def queue_has_done_for_h(harness, proc):
    return any(item[0] == 'done' and item[2] is proc for item in list(harness.output_queue.queue))
assert wait_queue_has(h, lambda: queue_has_done_for_h(h, p1)), 'нет done от p1'

# --- _start_run создаёт НОВЫЙ процесс P2 (тоже ждёт ввод) ---
p2 = spawn('import sys\nsys.stdout.write("p2-started\\n"); sys.stdout.flush()\nsys.stdin.readline()')
h.process = p2
threading.Thread(target=h._read_stream, args=(p2, p2.stdout, 'stdout'), daemon=True).start()
threading.Thread(target=h._watch_process, args=(p2,), daemon=True).start()

# --- теперь Tk-поллинг разбирает очередь, где лежит stale 'done' от p1 ---
h.drain_once()

# ГЛАВНАЯ ПРОВЕРКА: новый процесс НЕ обнулён stale-сообщением старого
assert h.process is p2, f'РЕГРЕССИЯ: новый процесс обнулён stale done старого (process={h.process})'
assert p2.poll() is None, 'P2 не должен быть завершён'
print('RACE: новый процесс выжил после stale done старого — OK')

# P2 жив и принимает ввод -> «перезапуск» реально состоялся
p2.stdin.write('go\n'); p2.stdin.flush()
assert p2.wait(timeout=5) == 0, 'P2 не принял ввод/не завершился штатно'
print('RESTART: P2 принял ввод и завершился штатно — OK')

# дочистим
for p in (p1, p2):
    if p.poll() is None:
        p.kill()


# ====== СЦЕНАРИЙ: обычное завершение НЕ теряет хвостовой вывод ======
h2 = Harness()
p = spawn('print("hello"); print("tail")')
h2.process = p
threading.Thread(target=h2._read_stream, args=(p, p.stdout, 'stdout'), daemon=True).start()
threading.Thread(target=h2._watch_process, args=(p,), daemon=True).start()
p.wait(timeout=5)
# ждём, пока в очередь попадут и вывод, и done
assert wait_queue_has(h2, lambda: queue_has_done_for_h(h2, p)), 'нет done при обычном завершении'
time.sleep(0.2)  # дать reader дочитать хвост
h2.drain_once()
text = ''.join(t for _tag, t in h2.appended)
assert 'hello' in text and 'tail' in text, f'потерян вывод: {text!r}'
assert h2.process is None, 'после done process должен стать None'
print('NORMAL: весь вывод (hello/tail) показан, process=None — OK')

# ====== СЦЕНАРИЙ: ручной стоп глушит «Процесс завершён, код» ======
h3 = Harness()
fake = object()                      # «процесс», помеченный как намеренно убитый
h3.process = None                    # как после stop_process
h3._silenced_procs.add(fake)
h3.output_queue.put(('status', '\nПроцесс завершён, код: 1\n', fake))
h3.output_queue.put(('done', None, fake))
h3.drain_once()
text3 = ''.join(t for _tag, t in h3.appended)
assert 'завершён' not in text3, f'не заглушён код завершения: {text3!r}'
assert fake not in h3._silenced_procs, 'пометка не снята по done'
print('SILENCE: «Процесс завершён» после ручного стопа подавлен — OK')

# ====== СЦЕНАРИЙ: _poll_output не работает на закрытии ======
h4 = Harness()
h4._closing = True
h4.output_queue.put(('stdout', 'x', object()))
h4.drain_once()
assert h4.appended == [] and h4._after_calls == [], 'poll работал при _closing'
print('CLOSING: _poll_output не трогает виджеты и не перепланируется — OK')

print('\nALL ASSERTIONS PASSED')
