Unwind
======

A simple solution to analysis and extract information from traceback

usage
-----

.. code:: python

   from unwind import Report

   with Report() as report:
       a = 1
       b = 2
       c = 'a'
       d = 1 + c

   print(report.errors)
   print(report.reports)

or

.. code:: python

   from unwind import get_report

   try:
       a = 1
       b = 2
       c = 'a'
       d = 1 + c
   except Exception as e:
       print(get_report(e))
