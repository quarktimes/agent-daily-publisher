#!/bin/bash
#
# Pre-commit hook — scan articles for leaked secrets before commit.
#
# Checks for:
#   - Database connection strings (jdbc:, mysql://, redis://, etc.)
#   - API keys and tokens (sk-proj, ghp_, gho_, 8CKv pattern)
#   - Private keys (-----BEGIN)
#   - Common sensitive patterns (password=, secret=)
#
# Usage:
#   cp scripts/pre-commit-check.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#

set -euo pipefail

ARTICLES_DIR="data/articles"
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color
HAS_ERROR=0

# Only check if articles directory has staged changes
STAGED_ARTICLES=$(git diff --cached --name-only -- "$ARTICLES_DIR" 2>/dev/null || true)
if [ -z "$STAGED_ARTICLES" ]; then
    exit 0
fi

PATTERNS=(
    # API Keys & Tokens
    'sk-proj[_-][A-Za-z0-9]'       # OpenAI keys
    'ghp_[A-Za-z0-9]{36}'          # GitHub PAT (old)
    'gho_[A-Za-z0-9]{36}'           # GitHub PAT (new)
    'xox[bp]-[A-Za-z0-9]'          # Slack tokens
    '8CKv[A-Za-z0-9]{20,}'         # Known API key pattern

    # Database connection strings
    'jdbc:(mysql|postgresql|sqlite|h2|oracle)://'
    'mysql://[^/]+@'
    'postgresql://[^/]+@'
    'mongodb://[^/]+@'
    'redis://[^:]+:[^@]+@'

    # Private keys
    '-----BEGIN (RSA|EC|OPENSSH|DSA|PRIVATE) KEY-----'

    # Common sensitive config
    'password=[^&\s]{3,}'
    'secret=[^&\s]{3,}'
    'connection\.string=[^&\s]'
)

for file in $STAGED_ARTICLES; do
    if [ ! -f "$file" ]; then
        continue
    fi

    for pattern in "${PATTERNS[@]}"; do
        matches=$(grep -nE "$pattern" "$file" 2>/dev/null || true)
        if [ -n "$matches" ]; then
            echo -e "${RED}⚠️  SECURITY ALERT: $file${NC}"
            echo "$matches"
            HAS_ERROR=1
        fi
    done
done

if [ $HAS_ERROR -eq 1 ]; then
    echo ""
    echo -e "${RED}❌  Commit blocked: potential secrets found in articles.${NC}"
    echo "   Review the lines above and remove any sensitive data."
    echo "   If these are false positives, use: git commit --no-verify"
    exit 1
fi

echo -e "${GREEN}✓  Article security check passed${NC}"
