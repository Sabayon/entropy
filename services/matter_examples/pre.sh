#!/bin/sh
echo "matter pre hook"
echo "BUILDER_REPOSITORY_ID = ${BUILDER_REPOSITORY_ID}"

is_mounted=$(mount | cut -d" " -f 3 | grep "/proc")
if [ -z "${is_mounted}" ]; then
	echo "mounting /proc, not mounted"
	mount -t proc proc /proc
fi
