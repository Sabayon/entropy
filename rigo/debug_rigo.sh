#!/bin/sh
export RIGO_DATA_DIR="./data"
export RIGO_ICON_PATH="./data/icons"
# GDB?
# exec gdb --args python rigo_app.py # --dumper --debug
export ETP_DEBUG=1
exec python rigo_app.py --dumper "${@}"
