#!/bin/sh
export MAGNETO_DATA_DIR="../data"
export MAGNETO_ICON_PATH="../data/icons"
export MAGNETO_PIXMAPS_PATH="../data/pixmaps"
export ETP_DEBUG=1
exec python magneto_app.py "${@}"
