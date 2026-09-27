# Agent context

An Agent has a directory `agents/<FLAMORIS_AGENT_KEY>/` with an `agent.toml`
manifest and one or more UTF-8 Markdown files. The manifest supplies the ordered
sections of the system prompt. No domain, project, or entity section is required.

```toml
version = 1

[[context]]
title = "Identity"
file = "identity.md"

[[context]]
title = "Customer support"
file = "support.md"
```

Each section requires a unique, nonempty title and a unique Markdown filename.
The file must be a basename in the same Agent directory (no absolute paths,
subdirectories, traversal, or escaping symlinks). An Agent needs 1–16 sections;
the manifest is limited to 16 KiB and all context text together to 32 KiB.
Empty or missing files fail startup with `invalid_agent_context`. The operator
can call `load_agent_context()` locally to see a specific validation error.
Choose the Agent key before creating the directory; only letters, digits,
hyphens, and underscores are accepted.

Runtime-owned rules about previous-conversation trust, unknown facts, and tool
boundaries are assembled by the program. Deployment-owned files supply identity,
speaking style, domain facts, entity relationships, and any other desired sections.
They are configuration supplied by the deployment operator; retrieved history is
separate untrusted JSON data in a lower-priority message, never a system section.
The database's historical `system_context` JSONB field records both the ordered
Agent sections and previous-conversation data for provenance; it does not grant
the previous conversation policy authority. See [the trust boundary](PROMPT_TRUST_BOUNDARY.md).

## Where files are loaded

- Source/editable checkout: the repository root supplies `.env` and `agents/`,
  independent of the current working directory.
- Installed wheel: process environment and the bundled synthetic
  `example-agent` resource are used by default. Arbitrary external Agent
  directories are not packaged automatically.
- Explicit deployment: export an absolute `FLAMORIS_AGENT_HOME` before launching
  the process. This directory supplies `.env` and `agents/<agent-key>/` and takes
  precedence. It does not fall back to the source checkout or bundled example
  when the selected Agent is missing.

For an existing deployment with `personality.md`, `flamoris.md`, and
`characters.md`, place `agent.toml` alongside those files and list only the
sections needed, in the intended order. For example, map personality to
`Identity`, project knowledge to `Domain knowledge`, and relationships to
`Entities and relationships`. The filenames may remain temporarily because
the loader uses manifest entries, not their names. Move universal trust rules
from private persona text to the runtime policy; review other content for
conflicts. There is no automatic legacy reader: deploy the manifest and runtime
update together, then verify the private Agent before restarting its service.
