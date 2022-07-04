import sys
from types import TracebackType
from typing import Dict, List, Union
import re
import faulthandler
import inspect
from pathlib import Path

from .typing import _ReportCode, _ReportExc, _ReportCall, TError, TReport, ReportFlag, _TraceContext, _eval_safe


def _handle_exc(slot: Dict, match: Dict[str, str], info: inspect.FrameInfo) -> _ReportExc:
    _locals = info.frame.f_locals
    _globals = info.frame.f_globals
    slot['flag'] = ReportFlag.ACTIVE
    exc_s = match['exc']
    if _mat := re.match(r"(?P<type>[^(]+)(?P<content>\(.*\))", exc_s):
        exc_t = _mat.groupdict()['type']
        slot['type'] = _globals.get(exc_t, _locals.get(exc_t, info.frame.f_builtins.get(exc_t, None)))
        slot['content'] = _mat.groupdict()['content'][1:-1]
    else:
        slot['content'] = exc_s
        slot['type'] = _globals.get(exc_s, _locals.get(exc_s, info.frame.f_builtins.get(exc_s, None)))
    return _ReportExc(**slot)


def _handle_call(
        slot: Dict, match: Dict[str, str],
        info: inspect.FrameInfo, previous: inspect.FrameInfo
) -> _ReportCall:
    _locals = info.frame.f_locals
    _globals = info.frame.f_globals
    _args = match['args']
    if _args.startswith("(") and _args.endswith(")"):
        _args = _args[1:-1]
    args = [c.strip() for c in _args.split(',') if c.strip()]
    paths = match['path'].strip().split()
    parts, end = paths[:-1], paths[-1]
    slot['flag'] = ReportFlag.AWAIT_AWAITABLE if "await" in parts else ReportFlag.CALL_CALLABLE

    _next = previous.function
    for key, value in {**_locals, **_globals, **info.frame.f_builtins}.items():
        if (inspect.isfunction(value) or inspect.ismethod(value)) and value.__name__ == _next:
            _next = key
            break
    for arg in args.copy():
        if _next not in arg:
            continue
        f_len = len(_next)
        start_index = arg.find(_next)
        _paths = arg[0:start_index + f_len].split()
        _parts, end = _paths[:-1], _paths[-1]
        slot['flag'] = ReportFlag.AWAIT_AWAITABLE if "await" in _parts else ReportFlag.CALL_CALLABLE
        if arg[start_index+f_len:].find('(') > -1 and (right := arg[start_index+f_len:].find(')')) > -1:
            args = [c.strip() for c in arg[start_index+f_len:][1:right].split(',') if c.strip()]
        else:
            args = []
        break

    _may_callable = None

    for p in end.split('.'):
        if obj := _globals.get(p, _locals.get(p, info.frame.f_builtins.get(p, None))):
            _may_callable = obj
        elif obj := getattr(_may_callable, p, None):
            _may_callable = obj
        else:
            _may_callable = p
    slot['callable'] = _may_callable
    call_args = {}
    try:
        sig = inspect.signature(_may_callable)
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
            call_args[_arg] = _locals.get(_arg, _eval_safe(_arg, _globals, _locals))
            args.remove(arg)
        elif _mat := re.match(r"(?P<key>.+)\s=\s(?P<value>.+)", arg):
            key, _arg = _mat.groups()
            call_args[key] = _locals.get(_arg, _eval_safe(_arg, _globals, _locals))
            args.remove(arg)
        elif arg in _locals:
            call_args[arg] = _locals[arg]
            args.remove(arg)

    for name, arg in zip(parameter, args.copy()):
        call_args[name] = _locals.get(arg, _eval_safe(arg, _globals, _locals))
        args.remove(arg)
    if args:
        call_args[vararg[0]] = [_locals.get(arg, _eval_safe(arg, _globals, _locals)) for arg in args]
    slot['args'] = call_args
    return _ReportCall(**slot)


def _handle_code(
        slot: Dict, info: inspect.FrameInfo,
        previous: inspect.FrameInfo
) -> Union[_ReportCode, _ReportCall]:
    _locals = info.frame.f_locals
    _globals = info.frame.f_globals
    content = info.code_context[0].strip()
    if content.endswith(":"):
        if mat := re.match("(async )?for .+ in (?P<iterable>.+?):$", content):
            match = mat.groupdict()['iterable']
            if _match := re.match(r"(?P<path>.+)\((?P<args>.*)\)", match):
                _slot = _handle_call(slot, _match.groupdict(), info, previous)
                _slot.flag = ReportFlag.ITER_ITERABLE
                return _slot
            slot['flag'] = ReportFlag.ITER_ITERABLE
            if _ch := _globals.get(match, _locals.get(match, info.frame.f_builtins.get(match, None))):
                slot['args'] = {match: _ch}
            else:
                slot['args'] = {"_unknown_name": _eval_safe(match, _globals, _locals)}
            return _ReportCode(**slot)
        if mat := re.match("(async )?with (?P<context>.+?)( )?(as .+)?$", content):
            match = mat.groupdict()['context']
            if _match := re.match(r"(?P<path>.+)\((?P<args>.*)\)", match):
                _slot = _handle_call(slot, _match.groupdict(), info, previous)
                _slot.flag = ReportFlag.ENTER_CONTEXT
                return _slot
            slot['flag'] = ReportFlag.ENTER_CONTEXT
            if _ch := _globals.get(match, _locals.get(match, info.frame.f_builtins.get(match, None))):
                slot['args'] = {match: _ch}
            else:
                slot['args'] = {"_unknown_name": _eval_safe(match, _globals, _locals)}
            return _ReportCode(**slot)
    if mat := re.match(r".*?await (?P<path>[^(=]+?)\s?$", content):
        slot['flag'] = ReportFlag.AWAIT_AWAITABLE
        paths = mat.groupdict()['path'].strip().split(' ')[-1].split('.')
        _may_callable = None
        for p in paths:
            if obj := _globals.get(p, _locals.get(p, info.frame.f_builtins.get(p, None))):
                _may_callable = obj
            elif obj := getattr(_may_callable, p):
                _may_callable = obj
            else:
                _may_callable = p
        slot['callable'] = _may_callable
        slot['args'] = {}
        return _ReportCall(**slot)
    slot['flag'] = ReportFlag.OPERATE
    _args = {}
    for text in content.split():
        if obj := _globals.get(text, _locals.get(text, info.frame.f_builtins.get(text, None))):
            _args[text] = obj
    slot['args'] = _args
    return _ReportCode(**slot)


def get_report(e: Union[BaseException, TracebackType], most_recent_first: bool = False) -> List[TReport]:
    """
    依据传入的错误或 Traceback 生成一个回溯帧和所有较低帧的记录列表

    Args:
        e: 需要进行回溯的错误或traceback
        most_recent_first: 是否让最近调用的帧的报告排在列表首位, 默认为 False (即 most recent call last)
    """
    _reports = []
    if isinstance(e, BaseException):
        e = e.__traceback__
    frames = inspect.getinnerframes(e)
    frames.reverse()
    for index, info in enumerate(frames):
        slot = {
            "info": _TraceContext(
                info.filename, info.lineno, info.function, info.code_context[0].strip(),
                info.frame.f_locals.copy()
            )
        }
        if mat := re.match(r"\s*raise (?P<exc>.+?)$", info.code_context[0]):
            _reports.append(_handle_exc(slot, mat.groupdict(), info))
        elif mat := re.match(r".*?(?P<path>[^(=]+?)\((?P<args>.*)\)\s?$", info.code_context[0]):
            _reports.append(_handle_call(slot, mat.groupdict(), info, frames[index - 1]))
        else:
            _reports.append(_handle_code(slot, info, frames[index - 1]))
    if not most_recent_first:
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
