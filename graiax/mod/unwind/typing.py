from enum import Enum
from types import TracebackType
from typing import Tuple, Type, NamedTuple, TypedDict, Callable, Optional, Dict, Any, Union
import ast

TError = Tuple[Type[BaseException], BaseException, TracebackType]


class ReportFlag(str, Enum):
    ACTIVE = "active"
    """此处代码主动抛出了一个错误"""

    CALL_CALLABLE = "call_callable"
    """此处正在调用一个可调用对象, 可能是函数, 也可能是实现了__call__的对象"""

    AWAIT_AWAITABLE = "await_awaiable"
    """此处正在等待协程对象, 即调用了__await__方法"""

    OPERATE = "operate"
    """此处代码在进行变量操作"""


class _TraceContext(NamedTuple):
    file: str
    line: int
    name: str
    code: str


class _ReportCall(TypedDict):
    type: ReportFlag
    info: _TraceContext
    callable: Optional[Callable]
    args: Dict[str, Any]


class _ReportExc(TypedDict):
    type: ReportFlag
    info: _TraceContext
    type: Optional[Type[BaseException]]
    content: Optional[str]


class _ReportCode(TypedDict):
    type: ReportFlag
    info: _TraceContext
    ast: ast.AST
    args: Dict[str, Any]


TReport = Union[_ReportExc, _ReportCall, _ReportCode]