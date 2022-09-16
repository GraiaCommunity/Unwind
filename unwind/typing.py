from enum import Enum
from types import TracebackType
from typing import Any, Callable, Dict, NamedTuple, Optional, Tuple, Type, Union, List

TError = Tuple[Type[BaseException], BaseException, TracebackType]


class ReportFlag(str, Enum):
    UNKNOWN = "unknown"
    """此处代码无法被获取, 请检查代码逻辑"""

    ACTIVE = "active"
    """此处代码主动抛出了一个错误"""

    CALL_CALLABLE = "call_callable"
    """此处代码正在调用一个可调用对象, 可能是函数, 也可能是实现了__call__的对象"""

    AWAIT_AWAITABLE = "await_awaitable"
    """此处代码正在等待协程对象, 即调用了__await__方法"""

    ENTER_CONTEXT = "enter_context"
    """此处代码正在进入一个上下文"""

    ITER_ITERABLE = "iter_iterable"
    """此处代码正在循环一个可迭代对象"""

    OPERATE = "operate"
    """此处代码在进行变量操作"""


class _TraceContext(NamedTuple):
    file: str
    line_index: int
    name: str
    codes: List[str]
    code_line: str
    locals: Dict[str, Any]

    def __repr__(self):
        code = "\n".join(self.codes)
        return (
            "TraceContext(\n"
            f"    file={self.file!r}\n"
            f"    line={self.line_index}\n"
            f"    name={self.name!r}\n"
            f"####====context====####\n"
            f"{code}\n"
            f"####====context====####\n"
            f"    error_line={self.code_line!r}\n"
            f"    locals={self.locals}\n"
            ")"
        )


class _BaseReport:
    flag: ReportFlag
    info: _TraceContext

    def __init__(self, info: _TraceContext, flag: Union[int, ReportFlag], **kwargs):
        self.info = info
        self.flag = ReportFlag(flag)
        for k, v in kwargs.items():
            self.__setattr__(k, v)

    def __repr__(self):
        return (
            "\n---------report--------\n"
            + "\n".join(
                f"{k} = {v}"
                for k, v in self.dict().items()
                if not isinstance(v, _BaseReport)
            )
            + "\n---------end-----------"
        )

    def dict(self):
        return vars(self)


class _ReportCall(_BaseReport):
    callable: Optional[Callable]
    args: Dict[str, Any]


class _ReportExc(_BaseReport):
    type: Optional[Type[BaseException]]
    content: Optional[str]


class _ReportCode(_BaseReport):
    args: Dict[str, Any]


TReport = Union[_ReportExc, _ReportCall, _ReportCode]


def _eval_safe(__s: str, __globals, __locals):
    try:
        return eval(__s, __globals, __locals)
    except Exception:
        return __s
