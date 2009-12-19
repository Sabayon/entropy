#!/bin/bash
echo "Number of commits per user:"
git shortlog -s -n | sort | uniq
echo
echo "Number of lines changed per user:"
printf "%30s %10s %10s %10s %10s \n" author added removed a+r a-r
printf "%30s %10s %10s %10s %10s \n" ^^^^^^ ^^^^^ ^^^^^^^ ^^^ ^^^
git log --pretty=format:%an | sort | uniq |
while read author; do
        LINES=$(git log --author="$author" --numstat --pretty=format: | gawk 'BEGIN {A=0; D=0}; /^[0-9]/ { A=A+$1; D=D+$2 }; END{print A, D, D+A, A-D}')
        printf "%30s %10s %10s %10s %10s \n" "$author" $LINES
done
