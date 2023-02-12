#!/bin/bash

version=$1
sed -i -e "s/^\([[:blank:]]*__version__ = \).*/\1'$version'/" luadoc/version.py
git add -A
git command  -m "bump version to $version"
git tag $version
git push
git push origin $version
