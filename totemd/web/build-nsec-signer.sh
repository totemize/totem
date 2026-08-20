#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
npm install --silent --no-audit --no-fund --prefix "$tmp" \
    esbuild@0.28.2 nostr-tools@2.23.1
NODE_PATH="$tmp/node_modules" "$tmp/node_modules/.bin/esbuild" \
    "$here/nsec-signer.source.js" --bundle --minify --format=iife \
    --platform=browser --legal-comments=inline \
    --outfile="$here/nsec-signer.js"
