#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Yuxi Version Bump Script
# =============================================================================
# Usage: ./scripts/bump-version.sh [--dev] <new_version>
# Example: ./scripts/bump-version.sh 0.6.2
# Example: ./scripts/bump-version.sh --dev 0.6.2.dev1
#
# Reads current version from backend/package/pyproject.toml and synchronizes
# all hardcoded version references across the project.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DEV_MODE=false
if [ "${1:-}" = "--dev" ]; then
    DEV_MODE=true
    shift
fi

if [ $# -ne 1 ]; then
    echo "Usage: $0 [--dev] <new_version>"
    echo "Example: $0 0.6.2"
    echo "Example: $0 --dev 0.6.2.dev1"
    exit 1
fi

NEW_VERSION="$1"

# Validate version format (supports x.y.z or x.y.z.devN)
if [[ ! "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(\.[a-zA-Z0-9]+)?$ ]]; then
    echo "Error: Invalid version format. Expected format like 0.6.2 or 0.6.2.dev1"
    exit 1
fi

PYPROJECT_FILE="${PROJECT_ROOT}/backend/package/pyproject.toml"
if [ ! -f "$PYPROJECT_FILE" ]; then
    echo "Error: Cannot find ${PYPROJECT_FILE}"
    exit 1
fi

CURRENT_VERSION=$(grep -E '^version[[:space:]]*=[[:space:]]*"' "$PYPROJECT_FILE" | head -1 | sed -E 's/^version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/')

if [ -z "$CURRENT_VERSION" ]; then
    echo "Error: Failed to read current version from ${PYPROJECT_FILE}"
    exit 1
fi

if [ "$CURRENT_VERSION" = "$NEW_VERSION" ]; then
    echo "Current version is already ${NEW_VERSION}, no update needed."
    exit 0
fi

echo "Ready to bump version from ${CURRENT_VERSION} to ${NEW_VERSION}"
echo "Affected files:"
echo "  - backend/package/pyproject.toml"
echo "  - backend/pyproject.toml"
echo "  - web/package.json"
echo "  - docker-compose.yml"
echo "  - docker-compose.prod.yml"
echo "  - backend/uv.lock"
echo "  - backend/package/uv.lock"
if [ "$DEV_MODE" = false ]; then
    echo "  - README.md"
    echo "  - README.en.md"
    echo "  - docs/intro/quick-start.md"
    echo "  - docs/.vitepress/theme/components/YuxiHome.vue"
fi
echo ""
read -rp "Confirm update? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 0
fi

# 1. Update Python package version
echo "→ Updating backend/package/pyproject.toml"
perl -pi -e "s/^version = \"[^\"]+\"/version = \"${NEW_VERSION}\"/" \
    "${PROJECT_ROOT}/backend/package/pyproject.toml"

# 2. Update workspace version
echo "→ Updating backend/pyproject.toml"
perl -pi -e "s/^version = \"[^\"]+\"/version = \"${NEW_VERSION}\"/" \
    "${PROJECT_ROOT}/backend/pyproject.toml"

# 3. Update web package version
echo "→ Updating web/package.json"
perl -pi -e "s/\"version\": \"[^\"]+\"/\"version\": \"${NEW_VERSION}\"/" \
    "${PROJECT_ROOT}/web/package.json"

# 4. Update docker-compose image tags
echo "→ Updating docker-compose.yml"
perl -pi -e "s/\\\$\\{YUXI_VERSION:-[^}]+\\}/\\\${YUXI_VERSION:-${NEW_VERSION}}/g" \
    "${PROJECT_ROOT}/docker-compose.yml"

echo "→ Updating docker-compose.prod.yml"
perl -pi -e "s/\\\$\\{YUXI_VERSION:-[^}]+\\}/\\\${YUXI_VERSION:-${NEW_VERSION}}/g" \
    "${PROJECT_ROOT}/docker-compose.prod.yml"

# 5. Update uv.lock files
echo "→ Updating backend/uv.lock"
perl -0pi -e "s/(^name = \"yuxi\"\nversion = \")[^\"]+/\${1}${NEW_VERSION}/m" \
    "${PROJECT_ROOT}/backend/uv.lock"
perl -0pi -e "s/(^name = \"yuxi-workspace\"\nversion = \")[^\"]+/\${1}${NEW_VERSION}/m" \
    "${PROJECT_ROOT}/backend/uv.lock"

echo "→ Updating backend/package/uv.lock"
perl -0pi -e "s/(^name = \"yuxi\"\nversion = \")[^\"]+/\${1}${NEW_VERSION}/m" \
    "${PROJECT_ROOT}/backend/package/uv.lock"

# 6. Update docs
if [ "$DEV_MODE" = false ]; then
    echo "→ Updating README.md"
    perl -pi -e "s/(git clone --branch v)[0-9]+\\.[0-9]+\\.[0-9]+(\\.[a-zA-Z0-9]+)?/\${1}${NEW_VERSION}/g" \
        "${PROJECT_ROOT}/README.md"

    echo "→ Updating README.en.md"
    perl -pi -e "s/(git clone --branch v)[0-9]+\\.[0-9]+\\.[0-9]+(\\.[a-zA-Z0-9]+)?/\${1}${NEW_VERSION}/g" \
        "${PROJECT_ROOT}/README.en.md"

    echo "→ Updating docs/intro/quick-start.md"
    perl -pi -e "s/(git clone --branch v)[0-9]+\\.[0-9]+\\.[0-9]+(\\.[a-zA-Z0-9]+)?/\${1}${NEW_VERSION}/g" \
        "${PROJECT_ROOT}/docs/intro/quick-start.md"

    echo "→ Updating docs/.vitepress/theme/components/YuxiHome.vue"
    perl -pi -e "s/(git clone --branch v)[0-9]+\\.[0-9]+\\.[0-9]+(\\.[a-zA-Z0-9]+)?/\${1}${NEW_VERSION}/g" \
        "${PROJECT_ROOT}/docs/.vitepress/theme/components/YuxiHome.vue"
else
    echo "→ Dev mode: skipping docs updates."
fi

# 7. Verification
echo ""
echo "Version bump completed:"
echo "  backend/package/pyproject.toml:"
grep -E "^version = \"" "${PROJECT_ROOT}/backend/package/pyproject.toml" | head -1 | sed 's/^/    /'

echo "  backend/pyproject.toml:"
grep -E "^version = \"" "${PROJECT_ROOT}/backend/pyproject.toml" | head -1 | sed 's/^/    /'

echo "  web/package.json:"
grep -E '"version"' "${PROJECT_ROOT}/web/package.json" | head -1 | sed 's/^/    /'

echo ""
echo "Next steps:"
echo "  1. Check git diff"
echo "  2. git add . && git commit -m 'chore(release): bump version to ${NEW_VERSION}'"
echo "  3. git tag v${NEW_VERSION}"
