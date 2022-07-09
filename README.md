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
info = _TraceContext(file='xxxxxx', line=7, name='<module>', code='d = 1 + c', locals={...})
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