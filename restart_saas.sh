#!/bin/bash
# Restart the bangumi-grillmaster SaaS API service
set -e
echo "Stopping..."
launchctl bootout gui/501/com.yoru.bangumi-grillmaster-saas-api 2>/dev/null || true
sleep 2
echo "Starting..."
launchctl bootstrap gui/501 /Users/yoru/Library/LaunchAgents/com.yoru.bangumi-grillmaster-saas-api.plist
sleep 2
echo "Testing login..."
curl -s -X POST http://localhost:8600/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"srzwyuu@gmail.com","password":"xjj20000908"}'
echo ""
echo "Done - open http://localhost:8600"
