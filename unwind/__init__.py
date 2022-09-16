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
    if event == "sys.excepthook":
        _base_report.errors = [args]
        _base_report.reports.clear()
        with suppress(StopIteration):
            tb: TracebackType = next(
                filter(lambda x: isinstance(x, TracebackType), args[0])
            )
            _base_report.reports = get_report(tb)
            for r in _callback:
                r(args, _base_report.reports)  # type: ignore
        return
    if event == "crash-report.exit":
        _base_report.errors = [args[0][0]]
        _base_report.reports = args[0][1]
        return


sys.addaudithook(_exc_hook)


def global_reports() -> List[TReport]:
    return _base_report.reports


def global_errors() -> List[TError]:
    return _base_report.errors


__all__ = [
    "Report",
    "ReportFlag",
    "TReport",
    "TError",
    "global_reports",
    "global_errors",
    "get_report",
    "add_report",
]
