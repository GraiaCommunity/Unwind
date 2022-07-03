import ctypes
from graiax.mod.unwind import Report

with Report() as report:
    ctypes.cast(1, ctypes.py_object)
    raise RuntimeError

print(report.errors)
print(report.reports)


def main():
    def foo(num: int):
        if num > 6:
            raise RuntimeError("A")
        return num ** 2

    b = 0
    for i in range(10):
        b += foo(i)
    return b


with Report() as report:
    a = main()
for rep in report.reports:
    print(rep)
