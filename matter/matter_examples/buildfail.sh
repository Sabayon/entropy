#!/bin/bash

if [ "${MATTER_PORTAGE_REPOSITORY}" = "gentoo" ]; then
	BUGZILLA_URL="https://bugs.gentoo.org"
	BUGZILLA_USER="lxnay@gentoo.org"
	BUGZILLA_PASSWORD=""
	#BUGZILLA_KEYWORDS="TINDERBOX"
	BUGZILLA_PRODUCT="Gentoo Linux"
	BUGZILLA_COMPONENT="Ebuilds"
	BUGZILLA_PRIORITY="Low"
	BUGZILLA_SEVERITY="QA"
elif [ "${MATTER_PORTAGE_REPOSITORY}" = "sabayon" ]; then
	BUGZILLA_URL="https://bugs.sabayon.org"
	BUGZILLA_USER="lxnay@sabayon.org"
	BUGZILLA_PASSWORD=""
	BUGZILLA_KEYWORDS="TINDERBOX"
	BUGZILLA_PRODUCT="Entropy"
	BUGZILLA_COMPONENT="Package"
	BUGZILLA_PRIORITY="Low"
	BUGZILLA_SEVERITY="normal"
else
	# don't file a bug then
	exit 0
fi

if [ ! -x "/usr/bin/bugz" ]; then
	echo "ouch, pybugz not installed"
	exit 1
fi

BUG_TEXT="Hello,
this is an automated report. So, please forgive me.
Package in subject has shown build failures on Sabayon Tinderbox.
Please find emerge --info =${MATTER_PORTAGE_FAILED_PACKAGE_NAME} below.
And hopefully the build log attached"

BUILD_LOG=$(echo -n "${MATTER_PORTAGE_BUILD_LOG_DIR}/${MATTER_PORTAGE_FAILED_PACKAGE_NAME}"*.log)
if [ -z "${BUILD_LOG}" ]; then
	echo "cannot find build log, wtf??"
	exit 1
fi
if [ ! -f "${BUILD_LOG}" ]; then
	echo "cannot find build log file"
	exit 1
fi

TINDERBOX_ID="$(date +%s)-${RANDOM}"
echo "Submitting bug with tinderbox_id: ${TINDERBOX_ID}"

/usr/bin/bugz -u "${BUGZILLA_USER}" -p "${BUGZILLA_PASSWORD}" --forget -b "${BUGZILLA_URL}" post \
	-t "${MATTER_PORTAGE_FAILED_PACKAGE_NAME} build failure [tinderbox_id:${TINDERBOX_ID}]" -d "${BUG_TEXT}" \
	--product "${BUGZILLA_PRODUCT}" --component "${BUGZILLA_COMPONENT}" \
	--append-command "emerge --info =${MATTER_PORTAGE_FAILED_PACKAGE_NAME}" \
	--priority "${BUGZILLA_PRIORITY}" --severity "${BUGZILLA_SEVERITY}" \
	--keywords ${BUGZILLA_KEYWORDS} --batch --default-confirm Y
if [ "${?}" != "0" ]; then
	echo "ouch, cannot report bug"
	exit 1
fi

# workaround the fact that pybugz doesn't return the newly created bug id in a reliable way
# use tinderbox_id
tmp_file=$(mktemp)
/usr/bin/bugz -q -u "${BUGZILLA_USER}" -p "${BUGZILLA_PASSWORD}" --forget -b "${BUGZILLA_URL}" search "tinderbox_id:${TINDERBOX_ID}" | \
	cut -d" " -f 1 | sed -r "s/\x1b\[\?1034h//" > "${tmp_file}"
if [ "${?}" != "0" ]; then
	echo "cannot execute search and retrieve submitted bug id"
	rm "${tmp_file}"
	exit 1
fi
submitted_bug_id=$(cat "${tmp_file}" | cut -d" " -f 1)
rm "${tmp_file}"
echo "Realized bug id: ${submitted_bug_id}"
if [ -z "${submitted_bug_id}" ]; then
	echo "cannot find submitted bug id, cannot attach build log"
	exit 1
fi

echo "Submitted bug to ${BUGZILLA_URL}, bug id: ${submitted_bug_id}"

# now attach the build log
/usr/bin/bugz -u "${BUGZILLA_USER}" -p "${BUGZILLA_PASSWORD}" --forget -b "${BUGZILLA_URL}" \
	attach "${submitted_bug_id}" "${BUILD_LOG}" -d "build log"
exit ${?}
