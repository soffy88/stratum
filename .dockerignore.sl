# Root-level .dockerignore for /home/soffy/projects build context
# Used by stratum/deploy/Dockerfile.sl (build context = /home/soffy/projects)

# Virtual environments — large, never needed in image
**/.venv/
**/venv/
**/__pycache__/
**/*.pyc
**/*.pyo
**/*.egg-info/
**/dist/
**/build/

# stratum-specific exclusions
stratum/stratum-web/
stratum/stratum-web/.next/
stratum/**/node_modules/
stratum/docs/
stratum/_hub/
stratum/concepts/
stratum/substrate/
stratum/experiments/
stratum/notes/
stratum/services/
stratum/.git/
stratum/deploy/logs/
stratum/.coverage
stratum/htmlcov/
stratum/.pytest_cache/

# platform exclusions — only needed packages, not tests/docs
platform/**/tests/
platform/**/docs/
platform/**/.git/
platform/**/.pytest_cache/
platform/**/htmlcov/
platform/**/*.lock
# Keep README.md (required by hatchling build backend); exclude verbose changelogs
platform/**/CHANGELOG.md
platform/**/RELEASE_POLICY.md
platform/**/ADR-*.md
platform/**/SELF_CHECK*.md
platform/**/Oprim-Final-List.md

# Other projects — not in image
helios-docker-bases/
helios-platform-docs/
helios-tape/
infra/
infrastructure/
packages/
secrets/
services/
tools/
d/
ccprompt/
