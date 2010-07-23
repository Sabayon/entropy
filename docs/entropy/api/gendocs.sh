#!/bin/sh
rm docs/* -rf
mkdir -p docs &> /dev/null
epydoc --config epydoc.cfg $@
