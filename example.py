import ctypes
from unwind import Report, get_report

with Report() as report:
    ctypes.cast(1, ctypes.py_object)
    raise RuntimeError

print(report.errors)


def main():
    def foo(num: int):
        if num > 6:
            raise RuntimeError("A")
        return num ** 2

    b = 0
    for i in range(10):
        b += foo(i)
    return b


with Report() as report1:
    a = main()
for rep in report1.reports:
    print(rep)

try:
    with Report(supress=False) as report1:
        a = main()
except RuntimeError as e:
    print(report1.errors)
    print(get_report(e))
    raise
