---
name: version
description: "Show the current taskflow version and tool count"
---

Read `pyproject.toml` from the taskflow project and extract the `version` field. Also count the registered MCP tools by calling `task_types` or inspecting the server. Report concisely:

- Taskflow version
- Number of MCP tools
- Number of workflow types
