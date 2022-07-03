import sys
from types import TracebackType
from typing import Dict, List, Union
import re
import faulthandler
import inspect
import ast
from pathlib import Path

from .typing import _ReportCode, _ReportExc, _ReportCall, TError, TReport, ReportFlag, _TraceContext


def _handle_exc(slot: Dict, match: Dict[str, str], info: inspect.FrameInfo) -> _ReportExc:
    _locals = info.frame.f_locals
    _globals = info.frame.f_globals
    slot['type'] = ReportFlag.ACTIVE
    exc_s = match['exc']
    if _mat := re.match(r"(?P<type>[^(]+)(?P<content>\(.*\))", exc_s):
        exc_t = _mat.groupdict()['type']
        slot['type'] = _globals.get(exc_t, _locals.get(exc_t, info.frame.f_builtins.get(exc_t, None)))
        slot['content'] = _mat.groupdict()['content'][1:-1]
    else:
        slot['content'] = exc_s
        slot['type'] = _globals.get(exc_s, _locals.get(exc_s, info.frame.f_builtins.get(exc_s, None)))
    return slot


def _handle_call(slot: Dict, match: Dict[str, str], info: inspect.FrameInfo) -> _ReportCall:
    slot['type'] = ReportFlag.CALL_CALLABLE
    _locals = info.frame.f_locals
    _globals = info.frame.f_globals
    args = [c.strip() for c in match['args'].strip('()').split(',') if c.strip()]
    if path := match.get('path'):
        paths = path.strip().split(' ')[-1].split(' .')
        _ch = None
        for p in paths:
            if obj := _globals.get(p, _locals.get(p, info.frame.f_builtins.get(p, None))):
                _ch = obj
            elif obj := getattr(_ch, p):
                _ch = obj
        slot['callable'] = _ch
        call_args = {}
        try:
            sig = inspect.signature(_ch)
            parameter = [
                param.name for param in sig.parameters.values() if param.kind in (
                    param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD)
            ]
            vararg = [param.name for param in sig.parameters.values() if param.kind == param.VAR_POSITIONAL]
            if not vararg:
                vararg.append("_unknown_name")
        except (ValueError, TypeError):
            parameter = []
            vararg = ["_unknown_name"]
        for arg in args.copy():
            if arg.startswith('*'):
                _arg = arg.lstrip('*')
                call_args[_arg] = _locals.get(_arg, eval(_arg, _globals, _locals))
                args.remove(arg)
            elif _mat := re.match(r"(?P<key>.+)\s=\s(?P<value>.+)", arg):
                key, _arg = _mat.groups()
                call_args[key] = _locals.get(_arg, eval(_arg, _globals, _locals))
                args.remove(arg)
            elif arg in _locals:
                call_args[arg] = _locals[arg]
                args.remove(arg)
        for name, arg in zip(parameter, args.copy()):
            call_args[name] = _locals.get(arg, eval(arg, _globals, _locals))
            args.remove(arg)
        if args:
            call_args[vararg[0]] = [_locals.get(arg, eval(arg, _globals, _locals)) for arg in args]
        slot['args'] = call_args  # type: ignore
    return slot


def _handle_await(slot: Dict, match: Dict[str, str], info: inspect.FrameInfo) -> _ReportCall:
    slot['type'] = ReportFlag.AWAIT_AWAITABLE
    paths = match['path'].strip().split(' ')[-1].split(' .')
    _locals = info.frame.f_locals
    _globals = info.frame.f_globals
    _ch = None
    for p in paths:
        if obj := _globals.get(p, _locals.get(p, info.frame.f_builtins.get(p, None))):
            _ch = obj
        elif obj := getattr(_ch, p):
            _ch = obj
    slot['callable'] = _ch
    slot['args'] = {}  # type: ignore
    return slot


def _handle_code(slot: Dict, info: inspect.FrameInfo) -> _ReportCode:
    slot['type'] = ReportFlag.OPERATE
    _locals = info.frame.f_locals
    _globals = info.frame.f_globals
    content = info.code_context[0].strip()
    slot['ast'] = ast.parse(content)  # type: ignore
    _args = {}
    for text in content.split():
        if obj := _globals.get(text, _locals.get(text, info.frame.f_builtins.get(text, None))):
            _args[text] = obj
    slot['args'] = _args  # type: ignore
    return slot


def get_report(e: Union[BaseException, TracebackType], most_recent_last: bool = False) -> List[TReport]:
    _reports = []
    if isinstance(e, BaseException):
        e = e.__traceback__
    for info in inspect.getinnerframes(e):
        slot: TReport = {  # type: ignore
            "info": _TraceContext(info.filename, info.lineno, info.function, info.code_context[0].strip())
        }
        if mat := re.match(r"\s*raise (?P<exc>.+?)$", info.code_context[0]):
            _reports.append(_handle_exc(slot, mat.groupdict(), info))
        elif mat := re.match(r".*?(?P<path>[^(=]+?)(?P<args>\([^()]*\))\s?$", info.code_context[0]):
            _reports.append(_handle_call(slot, mat.groupdict(), info))
        elif mat := re.match(r".*?await (?P<path>[^(=]+?)\s?$", info.code_context[0]):
            _reports.append(_handle_await(slot, mat.groupdict(), info))
        else:
            _reports.append(_handle_code(slot, info))
    if not most_recent_last:
        _reports.reverse()
    return _reports


class Report:
    errors: List[Union[TError, str]]
    reports: List[TReport]

    def __init__(self, supress: bool = True):
        self.errors = []
        self.reports = []
        self._path = Path("crash_report_cache.txt")
        self._supress = supress

    def __enter__(self):
        faulthandler.enable()
        sys.audit("crash-report.enter")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.audit("crash-report.exit", exc_type, exc_val, exc_tb)
        self.errors.append((exc_type, exc_val, exc_tb))
        if faulthandler.is_enabled():
            with self._path.open("w+") as f:
                faulthandler.dump_traceback(f)
            with self._path.open("r") as f:
                txt = f.read()
                if txt.strip():
                    self.errors.append(txt)
            self._path.unlink(True)
            faulthandler.disable()
        if exc_tb:
            self.reports = get_report(exc_tb)
        return exc_type is not None and self._supress


__all__ = ["Report", "get_report"]
