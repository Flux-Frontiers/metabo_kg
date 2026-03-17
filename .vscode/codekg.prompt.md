---
mode: 'agent'
description: 'Activate expert knowledge for installing, configuring, and using the CodeKG MCP server.'
---

# CodeKG Skill

Use expert knowledge for installing, configuring, and using the CodeKG MCP server.

Read and follow the instructions in `.claude/skills/codekg/SKILL.md`, then assist the user with their CodeKG request.

If the user provided a specific question or task (e.g., `query_codebase`), treat it as their specific question within the CodeKG domain.

If no specific task was provided, briefly summarize what CodeKG is and what you can help with, then ask what the user needs.
