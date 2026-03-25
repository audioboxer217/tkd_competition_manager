#!/usr/bin/env bash
# This script is used to switch between different environments (e.g., dev or prod).
# Usage: ./switch_env.sh [dev|prod]
set -e
ENV=$1
if [[ "$ENV" != "dev" && "$ENV" != "prod" ]]; then
  echo "Usage: $0 [dev|prod]"
  exit 1
fi

# Replace the .env link file with the appropriate environment file
rm .env && ln -sf "$ENV.env" .env
echo "Switched to $ENV environment"