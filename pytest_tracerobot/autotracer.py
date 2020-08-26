
#pylint: disable=too-many-instance-attributes,no-else-return,too-many-branches

import sys
import os
import traceback
from abc import ABC, abstractmethod

IS_DEBUG = False

class ITraceLogger(ABC): 

    @abstractmethod
    def enter_frame(self, frame, is_external): 
        pass

    @abstractmethod 
    def handle_exception(self, frame, exception, value, tb, is_first_occurrence): 
        pass

    @abstractmethod
    def exit_frame(self, frame, return_value):
        pass

class AutoTracer:
    """ This class implements a python call tracer that can provides "keyword"
        log output to tracerobot logs. The output is enabled on a call depth
        range that starts from the test function itself (tracer is enabled
        much earlier than that) and ends to first method that looks like a
        private method or a system lib call. 
        
        Config is a dictionary with: 
            'trace_privates': bool, true to trace in to functions starting with "_"
            'trace_paths': list of paths to follow
            'trace_silentpaths': list of paths to follow but which are not logged
        
        """

    def __init__(self, logger, config):
        self._loggers = [logger]
        self._depth = 0
        self._ctx = []
        self._is_exc_handled = False

        self._trace_privates = config['trace_privates'] if config else False
        self._trace_paths = []
        self._trace_silentpaths = []

        if 'trace_paths' in config:
            self._trace_paths += (config['trace_paths'] or [])

        if 'trace_silentpaths' in config:
            self._trace_silentpaths += (config['trace_silentpaths'] or [])

    def add_logger(self, logger): 
        self._loggers.append(logger)

    def start(self):
        self._ctx = []
        sys.settrace(self.trace)

    def stop(self):
        sys.settrace(None)

    def debug(self, msg):
        sys.settrace(None)
        depth = self._depth
        print("".ljust(depth), depth, ":", msg)
        sys.settrace(self.trace)

    class DummyCtx:
        def __init__(self):
            pass

        def handle_exc(self, arg, is_original):
            pass

        def finish(self, arg):
            pass

        def is_in_scope(self):
            return False


    class TraceCtx:

        def __init__(self, tracer, frame, in_scope, is_external):
            self._tracer = tracer
            self._frame = frame
            self._is_in_scope = in_scope

            if IS_DEBUG:
                self._debug("LOG", frame.f_code.co_name)
                
            self._log(lambda logger: logger.enter_frame(frame, is_external))
            
        def handle_exc(self, exc_info, is_original):
            (exception, value, tb) = exc_info

            if IS_DEBUG:
                self._debug("EXC", msg)

            self._log(lambda logger: logger.handle_exception(self._frame, exception, value, tb, is_original))

        def finish(self, return_value):
            if IS_DEBUG:
                self._debug("RET")

            self._log(lambda logger: logger.exit_frame(self._frame, return_value))
            
        def is_in_scope(self):
            return self._is_in_scope

        def _debug(self, *args):
            self._tracer.debug(" ".join([str(x) for x in args]))

        def _log(self, func): 
            for logger in self._tracer._loggers:
                func(logger)


    def trace(self, frame, event, arg):

        ret = self.trace 

        try:

            if event == "call":

                self._depth += 1

                name = frame.f_code.co_name
                path = frame.f_code.co_filename

                (in_scope, is_external, is_silent) = self.is_func_logged(name, path)
                if not is_silent and (in_scope or self.is_log_children()):
                    ctx = AutoTracer.TraceCtx(self, frame, in_scope, is_external)                    
                else:
                    # todo: optimize execution by disabling trace in sub-frames.
                    # however, this isn't so trivial as it looks, as
                    # the return event(s) needs to be handled properly.
                    # One way to do this would be to have a phased set of context handlers:
                    #  PreLogCtx: follows trace but doesn't log
                    #  TraceCtx: follow trace, do logging
                    #  DummyCtx, don't follow trace, don't log
                    ctx = AutoTracer.DummyCtx()

                self._ctx.append(ctx)

                self._is_exc_handled = False

            elif event == "exception":
                self._ctx[-1].handle_exc(arg, not self._is_exc_handled)
                self._is_exc_handled = True
                # for exceptions, exception event is handled first and then
                # return event

            elif event == "return":
                self._ctx[-1].finish(arg)
                self._ctx.pop()
                self._depth -= 1

            assert self._depth >= 0

        except Exception as err: 
            self.debug("Exception in tracer: " + str(err) + "\n" + traceback.format_exc())
            raise

        # Note: python docs say that the tracer function can return
        # an another tracer function instance here for the sub-scope
        # but it doesn't seem to be working like that in reality
        # (such sub-tracer was ignored when tried)

        return ret

    def is_func_logged(self, name, path):
        """ Returns tuple (in_scope, is_external, is_silent) """

        for silentpath in self._trace_silentpaths:
            if path.startswith(silentpath):
                return (False, False, True)

        if not self._trace_privates and name.startswith("_"):
            return (False, False, False)

        if name.startswith("__") and not name.startswith("__init__"):
            return (False, False, True)

        for libpath in self._trace_paths:
            if path.startswith(libpath):
                return (True, False, False)

        return (False, True, False)

    def is_log_children(self):
        return self._ctx and self._ctx[-1].is_in_scope()
