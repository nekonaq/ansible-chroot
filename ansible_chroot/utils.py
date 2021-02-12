from contextlib import contextmanager
import os
import sys
import curses
import termios
import collections


def flatten(value):
    # - https://stackoverflow.com/questions/952914/how-to-make-a-flat-list-out-of-list-of-lists
    return [
        item for sublist in value for item in (
            flatten(sublist)
            if isinstance(value, collections.Iterable) and not isinstance(sublist, (str, bytes))
            else (sublist,)
        )
    ]


def ensure_root():
    if os.getuid() != 0:
        raise PermissionError("You must be a root")


@contextmanager
def save_term_mode(*args, **kwargs):
    # print("BEGIN")
    isatty = sys.stdin.isatty()
    if isatty:
        tty_attrs = termios.tcgetattr(sys.stdin)
        curses.setupterm()
        term_rs2 = curses.tigetstr("rs2")
    try:
        yield
    finally:
        if isatty:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, tty_attrs)
            if term_rs2:
                curses.putp(term_rs2)
    # print("END")
