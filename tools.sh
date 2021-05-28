#!/bin/bash

BASEDIR=$(dirname "$0")
NO_ARGS=0
E_OPTERROR=85

cd $BASEDIR/tools
if [ $# -eq "$NO_ARGS" ]    # Script invoked with no command-line args?
then
    if [ -d "venv" ]; then
        echo "You must specify a task!"
        source ./venv/bin/activate && inv --list
    else
        echo "You must run './tools.sh bootstrap' first!"
    fi
else
    if [ $1 == "bootstrap" ]
    then
        echo "Bootstrapping tools..."
        rm -rf venv
        python3 -m venv venv
        source ./venv/bin/activate && pip install -r requirements.txt && pip install --upgrade pip
        echo "Tools successfully bootstrapped!"
    else
        source ./venv/bin/activate && inv $1 $2 $3
    fi
fi