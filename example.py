import ctypes
from unwind import Report, get_report
from devtools import debug

with Report() as report:
    ctypes.cast(1, ctypes.py_object)
    raise RuntimeError

print(report.errors)
print(report.reports)


def main(*args, **kwargs):
    def foo(num: int):
        if num > 6:
            raise RuntimeError(
                "A"
            )
        return num ** 2

    b = 0
    for i in range(10):
        b += foo(i)
    return b


with Report() as report1:
    a = main(
    )
for rep in report1.reports:
    print(rep)

try:
    with Report(supress=False) as report1:
        a = main(
            1, 2, 3,
            (
                f"assss"
                f"ddddd"
                f"ggggg{report1}"
            ),
            4,
            d="aaa".ljust(
                3, 'a'
            ),
            a=1, b=2, c=3,
        )
except RuntimeError as e:
    print(report1.errors)
    debug(get_report(e))
    raise
