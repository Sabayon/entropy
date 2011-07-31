#!/bin/sh
echo "auto-builder pre hook"
echo "BUILDER_REPOSITORY_ID = ${BUILDER_REPOSITORY_ID}"
echo "BUILDER_CHROOT_DIR = ${BUILDER_CHROOT_DIR}"
real_builder_chroot_dir=$(realpath "${BUILDER_CHROOT_DIR}")

is_mounted=$(mount | cut -d" " -f 3 | grep "${real_builder_chroot_dir}/proc")
if [ -z "${is_mounted}" ]; then
	echo "mounting /proc, not mounted"
	mount --bind /proc "${real_builder_chroot_dir}"/proc
fi

is_mounted=$(mount | cut -d" " -f 3 | grep "${real_builder_chroot_dir}/dev")
if [ -z "${is_mounted}" ]; then
	echo "mounting /dev, not mounted"
	mount --bind /dev "${real_builder_chroot_dir}"/dev
fi
