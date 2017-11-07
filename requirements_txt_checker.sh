#!/bin/bash

# Checks that the requirements.txt file is in sync with
# requirements.in and that there are no known vulnerabilities,
# and that there are no updated packages.

# Install the latest pip-tools and pyup.io's safety tool.
pip3 install -U pip-tools safety > /dev/null

# Flatten out all of the dependencies of our dependencies to
# a temporary file.
FN=$(tempfile)
pip-compile --generate-hashes --output-file $FN --no-header --no-annotate requirements.in > /dev/null

# The reverse-dependency metadata doesn't seem to be entirely
# accurate and changes nondeterministically? We omit it above
# with --no-annotate and remove it from a copy of our requirements.txt
# file before comparing.
FN2=$(tempfile)
cat requirements.txt \
	| python3 -c "import sys, re; print(re.sub(r'[\s\\\\]+# via .*', '', sys.stdin.read()));" \
	> $FN2

# Compare the requirements.txt in the repository to the one found by
# generating it from requirements.in.
if ! diff -B -u $FN $FN2; then
	rm $FN $FN2
	echo
	echo "requirements.txt is not in sync. Run requirements_txt_updater.sh."
	exit 1
fi
rm $FN $FN2
echo "requirements.txt is in sync with requirements.in."
echo

# Check packages for known vulnerabilities using pyup.io.
# Script exits on error.
safety check --bare -r requirements.txt
echo "No known vulnerabilities in Python dependencies."

# Check installed packages for anything outdated. Unfortunately
# this scans *installed* packages, so it assumes you are working
# in a development environment that's been set up and that you
# have no other installed packages because it will report updates
# on those too.
FN=$(tempfile)
pip3 list --outdated --format=columns > $FN
if [ $(cat $FN | wc -l) -gt 2 ]; then
	echo
	echo "Some packages are out of date:"
	echo
	cat $FN
	rm $FN
	exit 1
fi
rm $FN
