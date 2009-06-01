#!/bin/sh
rm docs/* -rf
epydoc --config epydoc.cfg $@
