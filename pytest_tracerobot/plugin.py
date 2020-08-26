import os
import traceback
import logging
from contextlib import AbstractContextManager, contextmanager
import pytest
import _pytest
from abc import ABC, abstractmethod
from enum import Enum

import tracerobot
from .utils import safe_repr, format_filename, format_exc, abs_paths
from .autotracer import ITraceLogger, AutoTracer

# Set to True to enable trace log of some hook calls to stdout
HOOK_DEBUG = True

def common_items(iter1, iter2):
    common = []
    for first, second in zip(iter1, iter2):
        if first != second:
            break
        common.append(first)
    return common

class TestPhase(Enum):

    SETUP = "setup"
    MAIN = "main"
    TEARDOWN = "teardown"

class ITestFunction(ABC):
    @abstractmethod
    def entry(self, phase, name, args=None, filename=None, linenumber=None, is_external=None, function=None):
        pass

    @abstractmethod
    def handle_exception(self, exc_location, exc_msg, is_first_occurrence):
        pass

    @abstractmethod
    def exit(self, return_value):
        pass

class ITestCase(ABC):

    @abstractmethod
    def entry(self, name, docstring, markers, function=None):
        pass

    @abstractmethod
    def exit(self, error_msg=None):
        pass


class ITestSuite(ABC):

    @abstractmethod
    def entry(self, name):
        pass

    @abstractmethod
    def exit(self):
        pass


class RobotTestFunction(ITestFunction): 

    PHASE_TO_KW_TYPE = {
        TestPhase.SETUP: "setup", 
        TestPhase.MAIN: "kw", 
        TestPhase.TEARDOWN: "teardown"
    }

    def __init__(self): 
        self._kw = None

    @staticmethod
    def _format_arg(name, value):
        return safe_repr(name) + "=" + safe_repr(value)

    def entry(self, phase, name, args=None, filename=None, linenumber=None, is_external=None, function=None):
        args_str = [ self._format_arg(name, value) for (name,value) in args ]
        full_name = name if not is_external else (
            format_filename(filename) + ":" + str(linenumber) + ":" + name)
        kw_type = RobotTestFunction.PHASE_TO_KW_TYPE[phase]
        self._kw = tracerobot.start_keyword(
            full_name, type=kw_type, args=args_str)

    def handle_exception(self, exc_location, exc_msg, is_first_occurrence):
        if is_first_occurrence:
            exc_kw = tracerobot.start_keyword(exc_location)
            tracerobot.end_keyword(exc_kw, error_msg=exc_msg)
        
        tracerobot.end_keyword(self._kw, error_msg=exc_msg)
        self._kw = None            

    def exit(self, return_value):
        if self._kw:
            tracerobot.end_keyword(self._kw, return_value=safe_repr(return_value))
        

class RobotTestCase(ITestCase):

    def __init__(self):
        self._testcase = None

    def entry(self, name, docstring, markers, function):
        self._testcase = tracerobot.start_test(
            name=name,
            doc=docstring,
            tags=markers)
    
    def exit(self, error_msg=None):
        tracerobot.end_test(self._testcase, error_msg)                

class RobotTestSuite(ITestSuite):

    def __init__(self): 
        self._suite = None

    def entry(self, name):
        self._suite = tracerobot.start_suite(name)        

    def exit(self):
        tracerobot.end_suite(self._suite)

class RobotFactory: 
    
    def new_suite(self): 
        return RobotTestSuite()
    
    def new_test(self):
        return RobotTestCase()

    def new_function(self):
        return RobotTestFunction()


class TraceStack:
    def __init__(self, factory):
        self._suite_stack = []
        self._cur_test = None
        self._func_stack = []
        self._factory = factory

    @property
    def current_path(self):
        return [path for path, _ in self._suite_stack]

    def start_suite(self, name) -> ITestSuite:
        suite = self._factory.new_suite()
        self._suite_stack.append((name, suite))        
        return suite

    def end_suite(self) -> ITestSuite:
        assert not self._cur_test
        assert not self._func_stack
        assert self._suite_stack
        _, suite = self._suite_stack.pop(-1)
        return suite
    
    def start_test(self) -> ITestCase:
        assert self._suite_stack
        assert not self._cur_test
        assert not self._func_stack
        self._cur_test = self._factory.new_test()
        return self._cur_test

    def end_test(self) -> ITestFunction:
        assert not self._func_stack
        assert self._cur_test
        test = self._cur_test
        self._cur_test = None
        return test

    def start_function(self) -> ITestFunction:
        func = self._factory.new_function()
        self._func_stack.append(func)
        return func

    def get_current_function(self) -> ITestFunction:
        assert self._func_stack
        return self._func_stack[-1]

    def end_function(self) -> ITestFunction:
        assert self._func_stack
        func = self._func_stack.pop()
        return func

    def finish(self): 

        while self._func_stack:
            func = self.end_function()
            func.handle_exception("???", "abnormal termination")
            func.exit(None)

        if self._cur_test:
            test = self.end_test()
            test.exit(error_msg="abnormal termination")

        while self._suite_stack:
            suite = self.end_suite()
            suite.exit()

        tracerobot.close()

class AutotraceLogger(ITraceLogger):

    def __init__(self, trace_stack):
        self._stack = trace_stack
        self._phase = TestPhase.MAIN

    @staticmethod
    def _format_arg(args, locals, i):
        arg = args[i]
        value = locals[arg]
        return safe_repr(arg) + "=" + safe_repr(value)

    def enter_frame(self, frame, is_external): 
        name = frame.f_code.co_name
        filename = frame.f_code.co_filename
        linenum = frame.f_code.co_firstlineno
        vars = frame.f_code.co_varnames
        locals = frame.f_locals        

        args = [(vars[i], locals[vars[i]]) for i in range(frame.f_code.co_argcount)]

        func = self._stack.start_function()
        func.entry(phase=self._phase, name=name, args=args, filename=filename, 
            linenumber=linenum, is_external=is_external)                
        self._phase = TestPhase.MAIN

    def handle_exception(self, frame, exception, value, tb, is_first_occurrence): 
        (exc_location, exc_msg) = format_exc(exception, value, tb)
        self._stack.get_current_function().handle_exception(exc_location, exc_msg, is_first_occurrence)

    def exit_frame(self, frame, return_value):
        func = self._stack.end_function()
        func.exit(return_value=safe_repr(return_value))

    def set_phase(self, phase):
        self._phase = phase


class TraceRobotPythonLogger(logging.Handler):

    LOG_LEVELS = {
        logging.CRITICAL:   "CRITICAL",
        logging.ERROR:      "ERROR",
        logging.WARNING:    "WARNING",
        logging.INFO:       "INFO",
        logging.DEBUG:      "DEBUG"
    }

    def __init__(self):
        super(TraceRobotPythonLogger, self).__init__()

    def handle(self, record):
        tracerobot.log_message(record.getMessage(), level=record.levelname)


class KeywordCtx(AbstractContextManager):
    """ A keyword context class that makes sure that started keywords
        get closed. """

    def __init__(self, name, kwtype="kw", args=None):
        super(AbstractContextManager, self).__init__()
        self._name = name
        self._kw = tracerobot.start_keyword(name, type=kwtype, args=args)
        self._error_msg = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        tracerobot.end_keyword(self._kw, error_msg=self._error_msg)

    def set_error_msg(self, error_msg):
        self._error_msg = error_msg


class TraceRobotPlugin:
    def __init__(self, config):

        print("TraceRobotPlugin")
        self.config = config        
        self._logger = TraceRobotPythonLogger()        
        self._stack = TraceStack(RobotFactory())
        self._autotracer_logger = AutotraceLogger(self._stack)        
        self._autotracer_config = {}
        self._autotracer = None
        print("TraceRobotPlugin end")

    def _get_error_msg(self, call):
        if call and call.excinfo:
            stack_summary = traceback.extract_tb(call.excinfo.tb)
            frames = traceback.format_list(stack_summary)
            msg = frames[-1] + "\n" + call.excinfo.exconly()
            return msg
        else:
            return None

    def _is_test_started(self, item):
        try:
            return item.rt_test_info is not None
        except AttributeError:
            return False

    def _is_test_with_setup_and_teardown(self, item):
        try:
            return item.rt_test_with_setup_and_teardown
        except AttributeError:
            return False

    def _get_test_error_msg(self, item):
        """ Return earlier error message(s) from setup / test body phases. """
        msg1 = None
        msg2 = None
        try:
            if item.rt_test_error_msg:
                msg1 = item.rt_test_error_msg
        except AttributeError:
            return None

        try:
            if item.rt_test_teardown_error_msg:
                msg2 = "Error in Teardown: " + item.rt_test_teardown_error_msg
        except AttributeError:
            return None

        if msg1 and msg2:
            return msg1 + " " + msg2
        elif msg1:
            return msg1
        elif msg2:
            return msg2
        else:
            return None

    def _has_test_setup(self, item):
        try:
            return item.rt_test_setup_info is not None
        except AttributeError:
            return False

    def _has_test_body(self, item):
        try:
            return item.rt_test_body_info is not None
        except AttributeError:
            return False

    def _has_test_teardown(self, item):
        try:
            return item.rt_test_teardown_info is not None
        except AttributeError:
            return False

    def _start_test_envelope(self, item, with_setup_and_teardown=False):
        """ test envelope consists of
                [setup keyword] + test function keyword + [teardown keywords]
                """
        if self._is_test_started(item):
            return

        markers = [marker.name for marker in item.iter_markers()]

        test = self._stack.start_test()
        test.entry(
            name=item.name,
            docstring=item.function.__doc__,
            markers=markers,
            function=item.function)
        item.rt_test_info = test
        item.rt_test_with_setup_and_teardown = with_setup_and_teardown
                
        self._start_auto_trace(TestPhase.SETUP)
        

    def _start_test_setup(self, item, fixturedef):
        assert self._is_test_with_setup_and_teardown

        if self._has_test_setup(item):
            self._finish_test_setup(item)

        # Applies to next keyword function called, returns automatically to "kw"
        self._autotracer_logger.set_phase(TestPhase.SETUP)
        
    def _finish_test_setup(self, item, call=None):
        if self._has_test_setup(item):
            error_msg = self._get_error_msg(call)
            item.rt_test_error_msg = error_msg
            item.rt_test_setup_info = None

    def _start_test_body(self, item):
        assert self._is_test_with_setup_and_teardown

    def _finish_test_body(self, item, call=None):

        error_msg = self._get_error_msg(call)
        item.rt_test_error_msg = error_msg

    def _start_test_teardown(self, item):
        assert self._is_test_with_setup_and_teardown
        self._autotracer_logger.set_phase(TestPhase.TEARDOWN)    
        func = self._stack.start_function()
        func.entry(name="fixture(s)", phase="teardown")
        item.rt_test_teardown_info = func

    def _finish_test_teardown(self, item, call=None):
        if self._has_test_teardown(item):
            error_msg = self._get_error_msg(call)
            test = self._stack.end_test()
            assert test == item.rt_test_teardown_info
            test.exit(error_msg=error_msg)
            item.rt_test_teardown_error_msg = error_msg
            item.rt_test_teardown_info = None

    def _finish_test_envelope(self, item, call=None):        
        self._stop_auto_trace()

        if self._is_test_started(item):
            if call.excinfo:
                error_msg = self._get_error_msg(call)
            else:
                error_msg = self._get_test_error_msg(item)

            test = self._stack.end_test()
            assert test == item.rt_test_info
            test.exit(error_msg=error_msg)
            
            item.rt_test_info = None


    # Initialization hooks

    def pytest_sessionstart(self, session):
        # note: this becomes after the root-level suite has been created
        tracerobot_config = {}
        for var in ["robot_output"]:
            tracerobot_config[var] = self.config.getoption(var)

        tracerobot.tracerobot_init(tracerobot_config)

        autotracer_config = {
            "trace_privates": self.config.getoption("trace_privates"),
            "trace_paths": [os.getcwd()] + abs_paths(self.config.getoption("trace_paths")),
            "trace_silentpaths": _pytest.__path__ + abs_paths(self.config.getoption("trace_disabled_paths"))
        }

        self._autotracer_config = autotracer_config

        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger().addHandler(self._logger)


    def pytest_sessionfinish(self, session, exitstatus):
        self._stack.finish()
        

    # Test running hooks

    def pytest_runtest_logstart(self, nodeid, location):
        """Each directory and test file maps to a Robot Framework suite.
        Because pytest doesn't seem to provide hook for entering/leaving
        suites as such, the current suite must be determined before each test.
        """
        #filename, linenum, testname = location
        filename, _, _ = location

        target = filename.split(os.sep)
        common = common_items(self._stack.current_path, target)

        while len(self._stack.current_path) > len(common):
            suite = self._stack.end_suite()
            suite.exit()

        assert self._stack.current_path == common

        while len(self._stack.current_path) < len(target):
            name = target[len(self._stack.current_path)]
            suite = self._stack.start_suite(name)
            suite.entry(name)

        assert self._stack.current_path == target


    def _start_auto_trace(self, phase=TestPhase.MAIN): 
        self._autotracer = AutoTracer(self._autotracer_logger, self._autotracer_config)
        self._autotracer_logger.set_phase(phase)
        self._autotracer.start()        
    
    def _stop_auto_trace(self):
        if self._autotracer: 
            self._autotracer.stop()

    @contextmanager
    def autotracer_running(self, phase):
        self._start_auto_trace(phase)
        yield
        self._stop_auto_trace()

    # Reporting hooks

    @pytest.hookimpl(hookwrapper=True)
    def pytest_fixture_setup(self, fixturedef, request):

        scope = fixturedef.scope    # 'function', 'class', 'module', 'session'

        if HOOK_DEBUG:
            # Note: run pytest with -s to see these
            print("\npytest_fixture_setup", fixturedef, request, request.node)

        if scope == 'function':
            # Function-scope fixtures typically mark start of a new test case
            # (except when there are multiple fixtures)
            item = request.node

            if not self._is_test_started(item):
                self._start_test_envelope(
                    item, with_setup_and_teardown=True)
                self._start_test_setup(item, fixturedef)

            yield
        else:
            # Module-scope fixtures may get run at any point of the test
            # execution. No need to start test envelope for them, but we
            # want to get them logged.
            with self.autotracer_running(TestPhase.SETUP):
                yield


    def pytest_runtest_call(self, item):
        pass

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_teardown(self, item, nextitem):
        # TODO: Figure out how to wrap around individual fixture teardowns
        # All fixture teardowns run during yield (if they exist)

        # Might have to re-implement pytest_runtest_teardown from _pytest.runner
        # or do some ugly monkeypatching of the Session, like this:
        #
        # def monkey_finalizer(self, colitem):
        #     ... call finalizers and wrap them here ...
        #
        # import types
        # state = item.session._setupstate
        # state._callfinalizers = types.MethodType(monkey_finalizer, state)
        #
        yield

    def pytest_runtest_makereport(self, item, call):

        #call.when: (post)"setup", (post)"call", (post)"teardown"
        #note: setup and teardown are called even if a test has no fixture

        if HOOK_DEBUG:
            print("\npytest_runtest_makereport", item, call)

        if call.when == "setup":
            #  finish setup phase (if any), start test body

            if self._is_test_with_setup_and_teardown(item):
                self._finish_test_setup(item, call)
                if not call.excinfo:
                    self._start_test_body(item)
                else:
                    self._finish_test_envelope(item, call)
            else:
                self._start_test_envelope(item)
                if call.excinfo:
                    self._finish_test_envelope(item, call)

        # pytest_runtest_call(item) gets called between "setup" and "call"

        elif call.when == "call":
            # test body called, enter teardown phase
            if self._is_test_with_setup_and_teardown(item):
                self._finish_test_body(item, call)
                self._start_test_teardown(item)
            else:
                self._finish_test_envelope(item, call)

        elif call.when == "teardown":
            # teardown finished
            if self._is_test_with_setup_and_teardown(item):
                self._finish_test_teardown(item, call)
                self._finish_test_envelope(item, call)


    def pytest_assertion_pass(self, item, lineno, orig, expl):

        if HOOK_DEBUG:
            print("\npytest_assertion_pass", item.fspath, lineno, orig)

        path = item.fspath
        fname = os.path.basename(path)
        name = fname + ":" + str(lineno) + ": assert"
        with KeywordCtx(name, args=[orig]) as assert_kw:
            tracerobot.log_message(expl)


    


        # TODO: should auto-tracing be configurable on/off?


#def pytest_configure(config):
    #plugin = TraceRobotPlugin(config)
    #config.pluginmanager.register(plugin)
