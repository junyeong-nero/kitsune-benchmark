---
name: kitsune-bench-aside
description: Use the Aside CLI REPL to operate a prepared local browser fixture in kitsune-benchmark. Not for browsing a user's existing session.
---

Use this skill only for an Aside benchmark task. Before opening a page, require the fixture origin and the benchmark-only local profile ID designated by the harness. If either is missing, stop; do not list profiles or choose the default one.

- Run `aside guide repl` for the guide shipped with the installed CLI. Do not install or update the product during a run.
- Send JavaScript on stdin to `aside repl --host local --profile <test-profile-id> --file -` using the supplied ID. Use only the fixture tabs prepared for this task. Do not discover or attach to the user's other tabs.
- Use the rendered fixture UI. Preserve the starting tabs. Do not read grading files, storage or network responses.
- Do not use `aside exec` or give a task prompt to bare `aside`: both delegate to another agent. If the REPL cannot reach the test profile, report that instead of switching profiles, hosts or models.
