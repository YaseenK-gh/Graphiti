import os
import random
import sys
import time
import tracemalloc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import support

from algorithms.generators import generate_graph_by_type
from algorithms.layouts import compute_layout
from algorithms.solvers import compute_chromatic_number
from core.constants import (CHROMATIC_TIMEOUT_MS, GRAPH_CONSTRAINTS, GRAPH_TYPES,
                            LAYOUT_TIMEOUT_MS, MEMORY_LIMIT_MB, MIN_FPS)
from core.graph_manager import GraphManager

CHROMATIC_SLACK_MS = 50

failures = []


def report(ok: bool, label: str):
    print(f"{'[PASS]' if ok else '[FAIL]'} {label}")
    if not ok:
        failures.append(label)


def process_rss_mb() -> float:
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

            counters = Counters()
            counters.cb = ctypes.sizeof(Counters)
            psapi = ctypes.WinDLL("psapi")
            kernel32 = ctypes.WinDLL("kernel32")
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
            return counters.WorkingSetSize / 1024 / 1024
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return float("nan")


def make_canvas():
    try:
        support.qapp()
        from ui.widgets.graph_canvas import GraphCanvas
    except ImportError:
        return None
    canvas = GraphCanvas()
    canvas.resize(1000, 800)
    canvas.show()
    return canvas


def test_generation_all_types():
    print("\nTesting generation of all 11 types at max n...")
    for graph_type in GRAPH_TYPES:
        n = GRAPH_CONSTRAINTS[graph_type][1]
        start = time.perf_counter()
        graph, error = GraphManager.generate_graph_safe(graph_type, n)
        elapsed = (time.perf_counter() - start) * 1000
        report(graph is not None, f"{graph_type} (n={n}): {elapsed:.0f}ms {error or ''}")


def test_layout_performance():
    print("\nTesting layout performance...")
    test_cases = [('PATH', 60), ('TREE', 50), ('BIPARTITE', 45), ('WHEEL', 35),
                  ('OUTERPLANAR', 40), ('CHORDAL', 40), ('TRIANGLE_FREE', 40),
                  ('NEAR_TRIANGULATION', 35), ('PLANAR', 45)]
    for graph_type, n in test_cases:
        vertices, edges = generate_graph_by_type(graph_type, n)
        start = time.perf_counter()
        compute_layout(graph_type, n, vertices, edges)
        elapsed = (time.perf_counter() - start) * 1000
        report(elapsed < LAYOUT_TIMEOUT_MS, f"{graph_type} (n={n}): {elapsed:.0f}ms")


def test_chromatic_timeout():
    print("\nTesting chromatic number computation...")
    for graph_type in ['TRIANGLE_FREE', 'NEAR_TRIANGULATION', 'PLANAR', 'CHORDAL']:
        lo, hi = GRAPH_CONSTRAINTS[graph_type]
        for n in sorted({min(25, hi), min(35, hi), hi}):
            vertices, edges = generate_graph_by_type(graph_type, n)
            start = time.perf_counter()
            chi = compute_chromatic_number(graph_type, n, edges)
            elapsed = (time.perf_counter() - start) * 1000
            ok = elapsed < CHROMATIC_TIMEOUT_MS + CHROMATIC_SLACK_MS and 2 <= chi <= 4
            report(ok, f"{graph_type} (n={n}): chi={chi}, {elapsed:.0f}ms")


def test_memory_stability(canvas):
    label = "with canvas rendering" if canvas else "generation only (UI not built yet)"
    print(f"\nTesting memory stability over 24 graphs ({label})...")
    tracemalloc.start()
    rng = random.Random(7)
    samples = []
    rss_start = process_rss_mb()
    for graph_num in range(24):
        graph_type = rng.choice(GRAPH_TYPES)
        lo, hi = GRAPH_CONSTRAINTS[graph_type]
        n = rng.randint(max(lo, 20), hi)
        graph = GraphManager.generate_graph(graph_type, n)
        if canvas is not None:
            canvas.set_graph(graph)
            support.qapp().processEvents()
        if graph_num % 6 == 5:
            current, peak = tracemalloc.get_traced_memory()
            samples.append(current)
            print(f"  Graph {graph_num + 1}: current {current / 1024 / 1024:.2f}MB, "
                  f"peak {peak / 1024 / 1024:.2f}MB, RSS {process_rss_mb():.0f}MB")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_end = process_rss_mb()
    report(peak < MEMORY_LIMIT_MB * 1024 * 1024,
           f"Python peak {peak / 1024 / 1024:.2f}MB < {MEMORY_LIMIT_MB}MB")
    report(rss_end < MEMORY_LIMIT_MB,
           f"Process RSS {rss_end:.0f}MB < {MEMORY_LIMIT_MB}MB (started at {rss_start:.0f}MB)")
    growth = (samples[-1] - samples[0]) / 1024 / 1024
    report(growth < 5, f"Python heap growth across run {growth:+.2f}MB (< 5MB)")
    if canvas is not None:
        from ui.widgets.graph_items import EdgeItem, VertexItem
        expected = len(canvas.graph.vertices) + len(canvas.graph.edges)
        graph_items = [i for i in canvas.graph_scene.items() if isinstance(i, (VertexItem, EdgeItem))]
        report(len(graph_items) == expected,
               f"Scene holds only the current graph ({len(graph_items)} vertices + edges)")


def test_render_fps(canvas):
    if canvas is None:
        print("\n(skipping FPS test: UI not built yet)")
        return
    print("\nTesting rendering speed at max complexity...")
    from PySide6.QtGui import QImage, QPainter
    for graph_type in ('COMPLETE_BIPARTITE', 'PLANAR', 'PATH'):
        graph = GraphManager.generate_graph(graph_type, GRAPH_CONSTRAINTS[graph_type][1])
        canvas.set_graph(graph)
        for v in graph.vertices:
            canvas.color_vertex(v, 0)
        image = QImage(canvas.viewport().size(), QImage.Format.Format_ARGB32_Premultiplied)
        frames = 60
        start = time.perf_counter()
        for _ in range(frames):
            painter = QPainter(image)
            canvas.render(painter)
            painter.end()
        fps = frames / (time.perf_counter() - start)
        report(fps >= MIN_FPS, f"{graph_type} (n={graph.n}, {len(graph.edges)} edges): {fps:.0f} FPS")


def main() -> int:
    test_generation_all_types()
    test_layout_performance()
    test_chromatic_timeout()
    canvas = make_canvas()
    test_memory_stability(canvas)
    test_render_fps(canvas)
    print("\n" + ("ALL PERFORMANCE CHECKS PASSED" if not failures
                  else f"{len(failures)} CHECK(S) FAILED:\n  " + "\n  ".join(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
