#!/bin/bash 

pytest --capture=no test.py $@
echo "Tests complete. There should be both failed and passed test cases."
rebot output.xml
