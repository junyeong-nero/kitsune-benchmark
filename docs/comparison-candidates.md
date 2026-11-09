# Browser MCP comparison candidates

[Documentation index](README.md) · [Current results](results/README.md)

This is a survey of **MCP servers/browser architectures**, not a catalog of
benchmark tasks. See [personal browsing](personal-browsing.md) for task design
and implementation status. Adding a surveyed server requires a separate adapter
and validation; none of the rows below is implicitly supported by the task runner.

Surveyed 2026-10-18 against upstream repositories/documentation. These are
**candidates, not implemented adapters or measured results**. Pin an exact release
or commit and re-check its current tool surface before adding any candidate.

Current measured targets are Kitsune and Microsoft's
[Playwright MCP](https://github.com/microsoft/playwright-mcp). The latter is not
the same implementation as ExecuteAutomation's similarly named project.

## Recommended candidates

| Priority / cohort | Candidate | Why compare it | Main constraint |
| --- | --- | --- | --- |
| A: Firefox-capable | [ExecuteAutomation Playwright MCP](https://github.com/executeautomation/mcp-playwright) | Different MCP tool design on a Playwright foundation; upstream documents Chromium/Firefox/WebKit support. Useful for separating the MCP interface from the browser automation library. | Verify its pinned Playwright can use the same private Firefox binary; never let automatic browser installation garbage-collect a shared cache. |
| A: Firefox-capable | [Selenium MCP](https://github.com/angiejones/mcp-selenium) | WebDriver-based alternative. Upstream lists Chrome, Firefox, Edge, and Safari; useful for a different automation architecture while retaining Firefox. | Validate a private geckodriver/browser pair, binary compatibility, viewport, and fresh profile. Support in a README is not proof our pinned Firefox works unchanged. |
| A: Chromium cohort | [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) | Official Chrome DevTools project: browser interaction, inspection, network/console and performance tooling. Strong local baseline. | Chrome/CDP, not the current Firefox environment. Disable usage statistics; use a dedicated profile, pin the browser/server, and audit any other outbound diagnostics. |
| A: Chromium cohort | [Browser MCP](https://github.com/BrowserMCP/mcp) | MCP server plus Chrome extension, adapted from Playwright MCP to drive an existing browser. A useful extension-based architecture comparison with Kitsune. | Provision a fresh test Chrome profile and extension connection rather than attaching to a personal session. |
| A: Chromium cohort | [Chrome MCP Server](https://github.com/hangwin/mcp-chrome) | Extension-based browser control with native Chrome APIs, content extraction, interaction and tab search. Another useful extension/server design. | Isolate native-messaging/extension resources; separately audit semantic-search embedding/model dependencies and any script tools. |
| A: Chromium cohort | [Browser Harness MCP](https://github.com/browser-use/browser-harness/blob/main/docs/MCP.md) | Browser Use's local stdio MCP, exposing browser helpers over local Chrome CDP. Click/type/read/screenshot primitives let the fixed outer model control the browser directly. | Use its MCP entry point, not the CLI/skill or cloud task agent. Inspect helper/code tools and freeze the tool implementation; no agent-written persistent helpers between trials. |
| B: browser-product cohort | [BrowserOS](https://github.com/browseros-ai/BrowserOS) | Chromium-based browser product with an MCP endpoint for external coding agents. Useful for comparing integrated browser/server architecture. | Drive it from the fixed Codex model, not an internal agent loop. A separate browser build and bundled services are extra variables. Do not import real logins or run automatic client/config setup against a normal Codex home. |
| B: local service or cloud cohort | [Steel MCP Server](https://github.com/steel-dev/steel-mcp-server) | Browser/session-oriented MCP; upstream documents both Steel Cloud and a self-hosted `STEEL_LOCAL=true` mode. | Cloud requires an API key; local mode waives the key but needs a separate steel-browser service. Include that service's resources; validate how it reaches the local task server. |

"Local" means there is a local operation path, **not a guarantee of no telemetry,
embedding downloads, hidden model calls, or future pricing changes**. Audit the
exact pinned mode before execution. No candidate was installed during this survey.

## Separate or lower-priority comparisons

| Candidate | Treatment |
| --- | --- |
| [Browser Use hosted MCP](https://browser-use.com/mcp) | Its hosted mode delegates a whole task to another agent and returns the result. That changes the model/agent being measured and introduces billed cloud/model usage. Do not mix it with local MCP primitive comparisons. Prefer Browser Harness MCP above for the current fixed-model experiment. |
| [Browserbase MCP](https://www.browserbase.com/mcp) | Current hosted service is a possible future cloud-browser track, subject to service/model charges and task-network access. The old [browserbase/mcp-server-browserbase](https://github.com/browserbase/mcp-server-browserbase) repository is archived and explicitly says it is not representative of the current production service. Do not treat that old implementation as the current product. |
| [Puppeteer reference MCP](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/puppeteer) | Historical baseline only: the reference server is in the archived, unmaintained servers repository. Avoid presenting it as a maintained primary contender. |
| [AgentDesk BrowserTools MCP](https://github.com/AgentDeskAI/browser-tools-mcp) | Primarily browser diagnostics/logging. Evaluate as a debugging tool, not as an interchangeable end-to-end task-control baseline without first confirming equivalent action tools. |
| [Aside](https://aside.com) / [ego(lite)](https://github.com/citrolabs/ego-lite) | Measured as **exhibition arms** on the external MiniWoB tasks only (Aside `repl`, ego `ego-browser nodejs` behind a wrapper): [2026-11-09 report](results/2026-11-09-exhibition-aside-ego-miniwob.md). Code-execution tools in vendor Chromium apps; not part of the head-to-head. |
| [agent-browser](https://github.com/vercel-labs/agent-browser) | A browser automation CLI, not a drop-in native MCP contender. A CLI adapter would change the current MCP-only tool policy and belongs in a separately labeled harness/tool track. |

## Recommended rollout

1. **Retain a Firefox cohort:** Kitsune, Microsoft Playwright MCP, then
   ExecuteAutomation Playwright MCP and Selenium MCP after exact-binary smoke
   validation. If exact binary compatibility fails, label the change rather
   than claiming the browser is fixed.
2. **Add a Chromium cohort:** first Chrome DevTools MCP, Browser MCP, and Chrome
   MCP Server; then Browser Harness MCP. Re-run the Microsoft Playwright baseline
   on the same Chromium build when possible. This is not the same cohort as the
   existing Firefox results.
3. **Separate product/cloud tracks:** BrowserOS, self-hosted Steel, and later
   hosted services. Browser builds, infrastructure and embedded agents must be
   visible independent variables, not silently attributed to MCP design.

### Required adapter checks

- Native schemas, one exposed MCP server name, fixed Codex/model/effort/prompt.
- Fresh profile, deterministic task/seed/reset, same effective viewport and budget.
- No personal sessions, default bridge conflicts, login imports or user-config edits.
- For the MiniWoB and personal UI-only tracks, audit script/evaluate/workflow/batch/code surfaces
  and unsafe navigation for every new server; different tool names need a fresh
  allowlist. Do not normalize all interfaces into one artificial tool schema.
- Identify whether any tool internally calls another LLM or an embedding API.
  With the current no-extra-API-budget constraint, avoid such modes unless a
  verified local alternative is selected.
- Register all owned process roots: browser, extension host, MCP, drivers,
  sidecar services, launcher and model/embedding helpers if any.
- Keep cold-start and warm-ready timing separate, counterbalance order, repeat
  task/seed pairs, and report execution errors apart from task failures.
- A remote browser cannot reach this harness's `127.0.0.1` MiniWoB/personal server without
  additional networking. Do not expose the token-bearing evaluator publicly just
  to make a cloud contender work. Remote resources are not local RSS measurements.

## Sources

Primary sources used for the table:

- https://github.com/executeautomation/mcp-playwright
- https://github.com/angiejones/mcp-selenium
- https://github.com/ChromeDevTools/chrome-devtools-mcp
- https://github.com/BrowserMCP/mcp
- https://github.com/hangwin/mcp-chrome
- https://github.com/browser-use/browser-harness/blob/main/docs/MCP.md
- https://browser-use.com/mcp
- https://github.com/browseros-ai/BrowserOS
- https://github.com/steel-dev/steel-mcp-server
- https://www.browserbase.com/mcp
- https://github.com/browserbase/mcp-server-browserbase
- https://github.com/modelcontextprotocol/servers-archived
- https://github.com/AgentDeskAI/browser-tools-mcp
- https://github.com/vercel-labs/agent-browser
