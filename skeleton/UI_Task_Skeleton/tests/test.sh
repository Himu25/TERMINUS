#!/bin/bash
set -e

# Verifier dependencies and the Playwright browser are installed in
# environment/Dockerfile. Do not install npm packages or Playwright here.

mkdir -p /logs/verifier

# Check if we're in a valid working directory
if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
  exit 1
fi

rm -rf /tmp/ui-task-tests
cp -R /tests /tmp/ui-task-tests
cd /tmp/ui-task-tests
ln -s /opt/ui-task-tests/node_modules node_modules
export PATH="/opt/ui-task-tests/node_modules/.bin:$PATH"

UNIT_EXIT=0
E2E_EXIT=0
npm run test || UNIT_EXIT=$?
npm run test:e2e || E2E_EXIT=$?

# Produce reward file (REQUIRED): pass only if both unit and E2E succeed
if [ "$UNIT_EXIT" -eq 0 ] && [ "$E2E_EXIT" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi

[ "$UNIT_EXIT" -eq 0 ] && [ "$E2E_EXIT" -eq 0 ]
