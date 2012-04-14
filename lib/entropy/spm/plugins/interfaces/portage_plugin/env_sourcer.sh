#!/bin/bash
# /bin/sh won't work

. ${1} || exit 1
eval echo \${${2}}
