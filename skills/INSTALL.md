# Installing the SpecHub skill

## Manual

With `npx`:

```bash
npx skills add https://github.com/alignium-labs/spechub/tree/main/skills/spechub
```

See the [`npx skills` documentation](https://github.com/vercel-labs/skills/blob/main/README.md) for reference.

With `gh`:

```bash
# Check version first - must be 2.90.0 or newer
gh --version

gh skill install alignium-labs/spechub skills/spechub
```

See the [`gh skill` documentation](https://github.com/cli/cli/blob/trunk/skills/gh-skill/SKILL.md) for reference.

## Automated

Most agents can install skills themselves. Ask your agent to install the skill
from <https://github.com/alignium-labs/spechub/tree/main/skills/spechub>.

## Updating

Re-run your install command to get the latest version.
