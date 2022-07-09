import sys
from types import TracebackType
from typing import Dict, List, Union
import re
import faulthandler
import inspect
from pathlib import Path
from io import BytesIO
import tokenize

from .typing import _ReportCode, _ReportExc, _ReportCall, TError, TReport, ReportFlag, _TraceContext, _eval_safe

PAT_RAISE = re.compile(r"\s*raise (?P<exc>.+?)$")
PAT_EXCEPTION = re.compile(r"(?P<type>[^(]+)(?P<content>\(.*\))")
PAT_CALL = re.compile(r".*?(?P<path>[^(=]+?)\((?P<args>.*)\)\s?$")
PAT_KEY_VALUE = re.compile(r"(?P<key>.+)\s?=\s?(?P<value>.+)")
PAT_ITER = re.compile("(async )?for .+ in (?P<iterable>.+?):$")
PAT_CONTEXT = re.compile("(async )?with (?P<context>.+?)( )?(as .+)?$")
PAT_AWAIT = re.compile(r".*?await (?P<path>[^(=]+?)\s?$")


def _tkn(source: str):
    source = source.encode("utf-8")
    source = BytesIO(source)
    try:
        yield from tokenize.tokenize(source.readline)
    except tokenize.TokenError:
        return


def _sub(input_: str) -> str:
    res: List[int] = []
    r_bracket: Dict[str, int] = {}
    rev_s = ''.join(reversed(list(input_)))

    for token in _tkn(rev_s):
        type_, string, (_, col), *_ = token
        if type_ == tokenize.OP:
            if string in {")", "]", "}"}:
                r_bracket[string] = 1 + r_bracket.get(string, 0)
            if string in {"(", "[", "{"}:
                if string == "(" and r_bracket.get(")"):
                    if r_bracket[')'] > 0:
                        r_bracket[')'] -= 1
                    else:
                        r_bracket.pop(')')
                elif string == "[" and r_bracket.get("]"):
                    if r_bracket[']'] > 0:
                        r_bracket[']'] -= 1
                    else:
                        r_bracket.pop(']')
                elif string == "{" and r_bracket.get("}"):
                    if r_bracket['}'] > 0:
                        r_bracket['}'] -= 1
                    else:
                        r_bracket.pop('}')
                else:
                    res.append(col)
            if string in {"=", ",", ";"} and not r_bracket:
                res.append(col)

    return input_[-min(res):]


def _split(input_: str) -> List[str]:
    left: List[int] = []
    right: List[int] = []
    strings = list(input_)

    for token in _tkn(input_):
        type_, string, (_, col), *_ = token
        if type_ == tokenize.OP:
            if string == "(":
                left.append(col)
            elif string == ")":
                right.append(col)
            elif string == "," and len(left) - len(right) == 1:
                strings[col] = '\1'
    return [
        c.strip() for c in ''.join(strings[left[0] + 1:right[min(len(left), len(right)) - 1]]).split('\1') if c.strip()
    ]


def _handle_exc(slot: Dict, match: Dict[str, str], info: inspect.FrameInfo) -> _ReportExc:
    _locals = info.frame.f_locals
    _globals = info.frame.f_globals
    slot['flag'] = ReportFlag.ACTIVE
    exc_s = match['exc']
    if _mat := PAT_EXCEPTION.match(exc_s):
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
    args = _split(f"({match['args']})")
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
        _paths = _sub(arg[:start_index + f_len]).split()
        _parts, end = _paths[:-1], _paths[-1]
        slot['flag'] = ReportFlag.AWAIT_AWAITABLE if "await" in _parts else ReportFlag.CALL_CALLABLE
        if arg[start_index + f_len:].find('(') > -1 and arg[start_index + f_len:].find(')') > -1:
            args = _split(arg[start_index + f_len:])
        else:
            args = []
        break

    _may_callable = _eval_safe(end, _globals, _locals)

    slot['callable'] = _may_callable
    call_args = {}
    try:
        param = inspect.signature(_may_callable).parameters
        names = [p.name for p in param.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        vararg = [p.name for p in param.values() if p.kind == p.VAR_POSITIONAL]
        if not vararg:
            vararg.append("_unknown_name")
    except (ValueError, TypeError):
        names = []
        vararg = ["_unknown_name"]

    for arg in args.copy():
        if arg.startswith('*'):
            _arg = arg.lstrip('*')
            call_args[_arg] = _locals.get(_arg, _eval_safe(_arg, _globals, _locals))
            args.remove(arg)
        elif _mat := PAT_KEY_VALUE.match(arg):
            key, _arg = _mat.groups()
            call_args[key] = _locals.get(_arg, _eval_safe(_arg, _globals, _locals))
            args.remove(arg)
        elif arg in _locals:
            call_args[arg] = _locals[arg]
            args.remove(arg)

    for name, arg in zip(names, args.copy()):
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
    if mat := PAT_ITER.match(content):
        match = mat.groupdict()['iterable']
        if _match := PAT_CALL.match(match):
            _slot = _handle_call(slot, _match.groupdict(), info, previous)
            _slot.flag = ReportFlag.ITER_ITERABLE
            return _slot
        slot['flag'] = ReportFlag.ITER_ITERABLE
        if _ch := _globals.get(match, _locals.get(match, info.frame.f_builtins.get(match, None))):
            slot['args'] = {match: _ch}
        else:
            slot['args'] = {"_unknown_name": _eval_safe(match, _globals, _locals)}
        return _ReportCode(**slot)
    if mat := PAT_CONTEXT.match(content):
        match = mat.groupdict()['context']
        if _match := PAT_CALL.match(match):
            _slot = _handle_call(slot, _match.groupdict(), info, previous)
            _slot.flag = ReportFlag.ENTER_CONTEXT
            return _slot
        slot['flag'] = ReportFlag.ENTER_CONTEXT
        if _ch := _globals.get(match, _locals.get(match, info.frame.f_builtins.get(match, None))):
            slot['args'] = {match: _ch}
        else:
            slot['args'] = {"_unknown_name": _eval_safe(match, _globals, _locals)}
        return _ReportCode(**slot)
    if mat := PAT_AWAIT.match(content):
        slot['flag'] = ReportFlag.AWAIT_AWAITABLE
        paths = mat.groupdict()['path'].strip().split(' ')[-1]
        _may_callable = _eval_safe(paths, _globals, _locals)
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


def get_report(
        e: Union[BaseException, TracebackType],
        most_recent_first: bool = False,
        whole_trace: bool = False
) -> List[TReport]:
    """
    依据传入的错误或 Traceback 生成一个回溯帧和所有较低帧的记录列表

    Args:
        e: 需要进行回溯的错误或traceback
        most_recent_first: 是否让最近调用的帧的报告排在列表首位, 默认为 False (即 most recent call last)
        whole_trace: 是否追踪所有帧 (即回溯较高帧), 默认为 False
    """
    _reports = []
    if isinstance(e, BaseException):
        e = e.__traceback__
    frames = inspect.getinnerframes(e)
    frames.reverse()
    if whole_trace:
        frames.extend(inspect.getouterframes(e.tb_frame))
    for index, info in enumerate(frames):
        if info.code_context is None:
            _info = _TraceContext(
                info.filename, info.lineno, info.function, '', info.frame.f_locals.copy()
            )
            _reports.append(_ReportCode(_info, ReportFlag.UNKNOWN, args={}))
            continue
        slot = {
            "info": _TraceContext(
                info.filename, info.lineno, info.function, info.code_context[0].strip(),
                info.frame.f_locals.copy()
            )
        }
        if mat := PAT_RAISE.match(info.code_context[0]):
            _reports.append(_handle_exc(slot, mat.groupdict(), info))
        elif mat := PAT_CALL.match(info.code_context[0]):
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
            sys.audit("crash-report.exit", self.errors[0], self.reports)
        return exc_type is not None and self._supress


__all__ = ["Report", "get_report"]
