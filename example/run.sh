#!/bin/bash

ARGS=$@
TESTS=${ARGS:=test*.py}

pytest --capture=no ${TESTS}
rebot output.xml
