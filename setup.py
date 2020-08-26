#!/usr/bin/env python3
from setuptools import setup

setup(
    name="pytest_tracerobot",
    version="0.4.0",
    packages=["pytest_tracerobot"],
    # the following makes a plugin available to pytest
    entry_points={"pytest11": ["tracerobot = pytest_tracerobot"]},
    # custom PyPI classifier for pytest plugins
    classifiers=["Framework :: Pytest"],
    install_requires=["tracerobot >= 0.3.1", "pytest >= 5.3.5"]
)
