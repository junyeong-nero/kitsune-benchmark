---
name: kitsune-bench-ego
description: Use the EgoLite CLI to operate a prepared local browser fixture in kitsune-benchmark. Not for browsing a user's existing session.
---

Use this skill only for an EgoLite benchmark task. Before opening a page, require the fixture origin and the test browser service and TaskSpace designated by the harness. If any are missing, stop; do not fall back to the default service or discover personal profiles.

- Run `ego-browser skill` for the guide shipped with the installed binary. Do not install or update the product during a run.
- Send JavaScript to `ego-browser --ego-server-name=<test-service> nodejs` using the supplied service name. Resume the designated TaskSpace; do not attach to other spaces or finish the harness's space.
- Use the rendered fixture UI. Preserve the starting tabs. Do not read grading files, storage or network responses. If a screenshot is needed, use only the PNG handoff supplied for this attempt.
- If the test browser does not answer, report the failed step. Do not use another browser, profile or model to finish the task.
