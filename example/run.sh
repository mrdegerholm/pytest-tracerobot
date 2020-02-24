#!/bin/bash

ARGS=$@
TESTS=${ARGS:=test*.py}

pytest --capture=no ${TESTS}
echo "Tests complete. All tests should be successful."
echo "Running rebot to get the HTML report and log file."
rebot output.xml
