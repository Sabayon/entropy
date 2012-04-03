#!/bin/sh

# Check current dir
[[ ! -d ".git" ]] && echo "this script must be executed from git repo root" && exit 1

# Check target tag
[[ -z "$1" ]] && echo "usage: $0 <new-version>" && exit 1

# Validate new version
new_tag="$1"
for cur_tag in `git tag`; do
	[[ "$cur_tag" == "$new_tag" ]] && echo "$new_tag already tagged" && exit 1
done

# Validate Entropy po files
( cd misc/po && make validate ) || exit 1

# Validate Rigo po files
( cd rigo/po && make validate ) || exit 1

# Update ChangeLog
echo "Updating ChangeLog for $new_tag"
for revision in client/revision server/revision sulfur/src/sulfur/revision lib/entropy/revision; do
    echo "$new_tag" > $revision
    git add $revision
done
git commit -m "Release Entropy $new_tag" client/revision server/revision sulfur/src/sulfur/revision lib/entropy/revision
git log > docs/ChangeLog
git add docs/ChangeLog
git commit -m "Tagging Entropy version $new_tag" docs/ChangeLog

# tag version
echo "Tagging version: $new_tag"
git tag $new_tag HEAD

# Push changes upstream
git push
git push --tags

ssh pkg.sabayon.org /sabayon/bin/tarball-new-entropy
