from tracerobot.rt_state import RtState
import os.path

class PathToSuiteAdapter:
    """ Each directory and test file maps to a Robot FW Suite.
        Because pytest doesn't seem to provide hook for entering/leaving
        suites as such, the current suite must be determined before each test.
        """

    def __init__(self):
        self._path_stack = []
        self._suite_stack = []

    @staticmethod
    def path_split(path):
        parts = []
        while len(path):
            (head, tail) = os.path.split(path)
            parts.append(tail)
            path = head
        parts.reverse()
        return parts

    @staticmethod
    def get_common_parts(p1, p2):
        common_parts = []
        for i in range(len(p1)):
            if i < len(p2) and p1[i] == p2[i]:
                common_parts.append(p1[i])
            else:
                break
        return common_parts

    def _enter_suite(self, name):
        adapter = RtState.get_adapter()
        self._path_stack.append(name)
        suite_id = '/'.join(self._path_stack)
        suite_info = adapter.start_suite(suite_id, name)
        self._suite_stack.append(suite_info)

        assert len(self._path_stack) == len(self._suite_stack)


    def _leave_suite(self, name):
        assert name == self._path_stack[-1]

        adapter = RtState.get_adapter()

        suite_info = self._suite_stack[-1]
        adapter.end_suite(suite_info)
        self._path_stack.pop()
        self._suite_stack.pop()

        assert len(self._path_stack) == len(self._suite_stack)


    def start_test(self, path):
        """ Each test directory and test maps to a suite.
            This function tracks which suites are being entered / left.
            """
        parts = self.path_split(path)
        cur_parts = [] + self._path_stack
        common_parts = self.get_common_parts(parts, cur_parts)

        while len(cur_parts) > len(common_parts):
            self._leave_suite(cur_parts[-1])
            cur_parts = cur_parts[0:-1]

        assert cur_parts == common_parts

        while len(cur_parts) < len(parts):
            newpart = parts[len(cur_parts)]
            self._enter_suite(newpart)
            cur_parts.append(newpart)

        assert cur_parts == parts

    def end_tests(self):
        """ Called at end of testing. """
        cur_parts = [] + self._path_stack

        while len(cur_parts):
            self._leave_suite(cur_parts[-1])
            cur_parts.pop()


g_path_to_suite = PathToSuiteAdapter()


def pytest_configure():
    # todo add logfile name setting option with pytest_addoption()
    RtState.init(logfile="output.xml")


def pytest_sessionstart(session):
    pass


def pytest_collect_directory(path, parent):
    pass


def pytest_collect_file(path, parent):
    pass


def pytest_runtest_logstart(nodeid, location):
    global g_path_to_suite
    g_path_to_suite.start_test(location[0])


def pytest_runtest_logfinish(nodeid, location):
    pass


def pytest_fixture_setup(fixturedef, request):

    adapter = RtState.get_adapter()
    adapter.start_setup()

    # tbd figure out this shit
    # target: get fixture setup and teardown code logged under
    # "setup" and "teardown" keywords if possible
    return None

    gen = fixturedef.func() #may return a generator


def pytest_runtest_call(item):
    adapter = RtState.get_adapter()
    item.rt_test_info = adapter.start_test(item.name)


def pytest_runtest_makereport(item, call):

    if not call.when == "call":
        return

    assert item.rt_test_info

    error_msg = None
    if call.excinfo:
        error_msg = call.excinfo.exconly()

    adapter = RtState.get_adapter()
    adapter.end_test(item.rt_test_info, error_msg)


def pytest_sessionfinish(session, exitstatus):

    global g_path_to_suite
    g_path_to_suite.end_tests()

    RtState.close()

    # todo: optionally run rebot by some option (use pytest_addoption)
