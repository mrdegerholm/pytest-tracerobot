
#pylint: disable=no-else-return

from contextlib import contextmanager
import traceback
import os
import os.path

@contextmanager
def catch_exc():
    try:
        yield
    except Exception as exc:
        print(exc)


def function_name(func):
    in_module = hasattr(func, '__module__')
    is_member = hasattr(func, '__self__')

    if is_member:
        name = func.__func__.__qualname__
    else:
        name = func.__qualname__

    if in_module:
        name = func.__module__ + '.' + name

    return name


def instance(func):
    if hasattr(func, '__self__'):
        return [str(func.__self__)]
    else:
        return []

def safe_repr(x): 
    try: 
        return repr(x)
    except: 
        return "[" + type(x).__name__ + "]"


def format_filename(filename): 
    cwd = os.getcwd()
    if filename.lower().startswith(cwd.lower()):
        return "." + os.path.join(".", filename[len(cwd):])
    else:
        return filename

def format_args(*args, **kwargs):
    return ([repr(a) for a in args] +
            ['{!r}={!r}'.format(k, v) for k, v in kwargs.items()])

def format_exc(exc, value, tb):
    stack_summary = traceback.extract_tb(tb)

    if not stack_summary: 
        exc_source = "<unknown location>"
    else:
        frame0 = stack_summary[0]
        exc_class_name = value.__class__.__name__
        exc_file = os.path.basename(frame0.filename)
        exc_source = exc_file + ":" + str(frame0.lineno) + ": " + exc_class_name

    frames = traceback.format_list(stack_summary)
    msg = ""
    if frames:
        msg = str(frames[-1]) + "\n"
    msg += str(traceback.format_exception_only(exc, value))

    return (exc_source, msg)

def abs_paths(paths): 
    if not paths: 
        return []

    return [ os.path.abspath(path) for path in paths ]
    