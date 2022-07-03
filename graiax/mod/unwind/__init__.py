from typing import List, Callable, Any
from contextlib import suppress
from types import TracebackType
import sys

from .typing import TError, TReport, ReportFlag
from .main import Report, get_report

_base_report = Report(False)
_callback: List[Callable[[TError, List[TReport]], Any]] = []


def add_report(target: Callable[[TError, List[TReport]], Any]):
    _callback.append(target)


def _exc_hook(event, *args):
    if event in ["sys.excepthook", "crash-report.exit"]:
        _base_report.errors = [args]
        _base_report.reports.clear()
        with suppress(StopIteration):
            tb: TracebackType = next(filter(lambda x: isinstance(x, TracebackType), args[0]))
            _base_report.reports = get_report(tb)
            for r in _callback:
                r(args, _base_report.reports)  # type: ignore
        return


sys.addaudithook(_exc_hook)


def global_reports():
    return _base_report.reports


def global_errors():
    return _base_report.errors


__all__ = ["Report", "ReportFlag", "TReport", "TError", "global_reports", "global_errors", "get_report", "add_report"]


if __name__ == '__main__':
    import ctypes

    with Report() as report:
        ctypes.cast(1, ctypes.py_object)
        raise RuntimeError

    print(report.errors)
    print(report.reports)


    def main():
        def test(num: int):
            if num > 6:
                raise RuntimeError("A")
            return num ** 2

        b = 0
        for i in range(10):
            b += test(i)
        return b


    with Report() as report:
        a = main()
    for rep in report.reports:
        print(rep)
