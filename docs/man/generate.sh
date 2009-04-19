#!/bin/sh
for file in *.pod; do
	manfile="man1/${file/.pod/}.1"
	pod2man -c "Entropy" ${file} > ${manfile}
	[[ "${?}" == "0" ]] && echo ${manfile} generated
done
