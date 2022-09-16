# Unwind

A simple solution to analysis and extract information from traceback

## install

```bash
pip install unwind
```

## usage

```python
from unwind import Report

with Report() as report:
    a = 1
    b = 2
    c = 'a'
    d = 1 + c

print(report.errors[0])
print(report.reports[0])

'''
(<class 'TypeError'>, TypeError("unsupported operand type(s) for +: 'int' and 'str'"), <traceback object at xxxxx>)
---------report--------
info = TraceContext(
    file='D:/Download/Projects/Unwind/example.py'
    line=59
    name='<module>'
####====context====####
    b = 2
    c = 'a'
    d = 1 + c

print(report.errors[0])
####====context====####
    error_line='d = 1 + c'
    locals={'__name__': '__main__', '__doc__': None, '__package__': None, '__loader__': <_frozen_importlib_external.SourceFileLoader object at 0x0000020F11200910>, '__spec__': None, '__annotations__': {}, '__builtins__': <module 'builtins' (built-in)>, '__file__': 'D:/Download/Projects/Unwind/example.py', '__cached__': None, 'Report': <class 'unwind.main.Report'>, 'report': <unwind.main.Report object at 0x0000020F112D86D0>, 'a': 1, 'b': 2, 'c': 'a'}
)
flag = operate
args = {'c': 'a'}
---------end------
'''
```

or

```python
from unwind import get_report

try:
    a = 1
    b = 2
    c = 'a'
    d = 1 + c
except Exception as e:
    print(get_report(e))

```