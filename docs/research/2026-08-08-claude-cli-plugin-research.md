# Claude CLI plugin landscape — research report

Date: 2026-08-08
Method: 5 Sonnet web-search agents + 8 Sonnet source deep-reads (deep-research
workflow), followed by direct Fable-level verification: every star count below
re-checked against the GitHub API on 2026-08-08; install count and niche leads
re-fetched by hand.

## The three Anthropic marketplaces (verified)

| Marketplace | Repo | Stars | What it is |
|---|---|---|---|
| `claude-plugins-official` | anthropics/claude-plugins-official | 33,270 | Auto-added to every session. `/plugins` dir = Anthropic-authored; `/external_plugins` = vendor-built (GitHub, Figma, Atlassian, context7…), Anthropic-approved only |
| `claude-code-plugins` | anthropics/claude-code | 140,702 | Demo marketplace inside the main repo: 13 plugins, all Anthropic-authored |
| `claude-community` | anthropics/claude-plugins-community | 340 | Third-party submissions, Anthropic-screened, not Anthropic-authored |

"In the official marketplace" ≠ "Anthropic-created": the `author` / source
field is the discriminator.

## Anthropic-authored plugins (the preference set)

Verified Anthropic-built, from the two official marketplace.json files:
`agent-sdk-dev`, `claude-code-setup`, `claude-md-management`*,
`claude-security`, `code-modernization`, `code-review`, `code-simplifier`,
`commit-commands`*, `explanatory-output-style`, `feature-dev`*,
`frontend-design`, `hookify`, `learning-output-style`, `mcp-server-dev`,
`mcp-tunnels`, `plugin-dev`, `pr-review-toolkit`*, `ralph-wiggum`,
`security-guidance`, plus the full LSP suite (pyright-lsp, clangd-lsp,
rust-analyzer-lsp, …).

\* already installed in this project — our Anthropic set is current.

**Notable absence (verified):** Anthropic ships no brainstorming/spec plugin,
and nothing for HPC, Fortran, or climate/earth-science workflows.

## Popularity ranking (GitHub API, 2026-08-08)

| Plugin | Stars | Origin | Note |
|---|---|---|---|
| superpowers | 269,167 | community — Jesse Vincent (obra) | **1,009,371 installs** per claude.com/plugins/superpowers; brainstorming, TDD, systematic-debugging, writing-plans. Also installs on Codex CLI, Cursor, Gemini CLI, Copilot CLI |
| ECC (Everything Claude Code) | 238,747 | community — affaan-m | 67 agents / 284 skills / 94 commands; plan-first + fresh-context review; cross-harness (Claude Code, Codex, Cursor, …). Complements rather than duplicates superpowers |
| spec-kit | 125,862 | GitHub (Microsoft) | Spec-driven development toolkit; the concept's other flagship, CLI-agnostic |
| caveman | 96,832 | community | Terse-output plugin (~65% fewer output tokens) |
| claude-mem | 90,078 | community | Cross-session compressed memory |
| context7 | 60,420 | Upstash; in official marketplace as external | Live library docs |
| wshobson/agents | 38,617 | community | 80+ specialist subagents |

The brainstorming hypothesis is **confirmed**: superpowers is #1 ecosystem-wide
by stars and installs, and brainstorming is its flagship skill. No
Anthropic-authored equivalent exists.

## Niche finds relevant to this project

- **beamer-skill** (Noi1r, 324 stars, MIT) — Claude Code skill for authoring,
  compiling (3-pass XeLaTeX), and reviewing beamer decks: layout audits, TikZ
  review, per-slide content bounds, PDF visual verification. Install: copy into
  `~/.claude/skills/`. Directly relevant to the intent_to_evidence deck.
- **nvidia-skills** (NVIDIA, 2,823 stars, active) — distributed via the
  Anthropic community marketplace; GPU/CUDA-leaning scientific skills.
- **claude-code-my-workflow** (pedrohcgs, 1,467 stars) — academic research
  workflows (econ-leaning).
- **CLIO Kit / claude-code-4-science** (IOWarp) — tiny (26 stars) but the only
  explicit HPC/science attempt found.

## Codex CLI comparison

- Extensibility surface: `AGENTS.md` + skills + MCP servers + plugins;
  official spec/examples repo **openai/plugins** (4,993 stars).
- Ecosystem is younger and list-driven: composio-community/awesome-codex-skills
  (15,705 stars), unofficial codex-marketplace.com (~155 plugins, 25
  OpenAI-published).
- Cross-pollination is the story: **superpowers and ECC both install on Codex
  CLI** — the workflow layer is becoming harness-portable while the plugin
  protocol itself stays per-CLI.

## Caveats

- ECC's deep-read agent returned garbage; its row above comes from my direct
  re-fetch of the README, and its skill/command counts move fast.
- claude.com/plugins install counts are self-reported by the directory; no
  independent check exists.
- Star counts are a popularity proxy that favors general-purpose over niche;
  beamer-skill's 324 stars understate its fit for this project.
