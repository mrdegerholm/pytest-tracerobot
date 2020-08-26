from .plugin import TraceRobotPlugin

def pytest_configure(config):
    plugin = TraceRobotPlugin(config)
    config.pluginmanager.register(plugin)

def pytest_addoption(parser):    
    group = parser.getgroup('TraceRobot')
    group.addoption(
        '--robot-output',
        default='output.xml',
        help='Path to Robot Framework XML output'
    )
    group.addoption(
        '--trace-privates',
        default=False,
        action='store_const',
        const=True,
        help='If set, also auto trace private method.'
    )
    group.addoption(
        '--trace-paths',
        nargs="*",
        help='List of paths for which the autotracer is enabled. Defaults to cwd.'
    )

    group.addoption(
        '--trace-disabled-paths',
        nargs="*",
        help='List of paths for which the autotracer is silenced.'
    )    