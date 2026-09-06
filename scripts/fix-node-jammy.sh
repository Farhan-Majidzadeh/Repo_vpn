#!/usr/bin/env bash
set -euo pipefail
# Fixes NodeSource Node.js conflict with Ubuntu Jammy's old libnode-dev package.
# Repo_vpn itself does not require Node.js.
export DEBIAN_FRONTEND=noninteractive
apt-get remove -y libnode-dev libnode72 nodejs npm || true
apt-get -f install -y
apt-get autoremove -y
apt-get clean
rm -f /var/cache/apt/archives/nodejs_*.deb
apt-get update
apt-get install -y nodejs
node --version
npm --version
