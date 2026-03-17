---
mode: 'agent'
description: 'Enforce the Agent-First Protocol: delegate work to specialist subagents, avoid reading many files directly or writing implementation code inline.'
---

# Protocol Enforcement

The **Agent-First Protocol** is now active.

## Command Argument Handling

If a task description was provided (e.g., `fix the login bug`), auto-detect the task type and route immediately. If no argument, follow interactive protocol below.

**Auto-Detection Logic:**

| Task Type | Keywords | Agent to Invoke |
|-----------|----------|-----------------|
| DEFECT | bug, fix, broken, error, crash, issue, not working, failing | `qa` |
| EXPERIENCE | UI, UX, feature, design, user, flow, modal, form, page, screen | `sd` |
| TECHNICAL (default) | architecture, refactor, API, backend, database, performance, or anything else | `ta` |

---

## CRITICAL: Token Efficiency Rules

**You should NEVER:**
- Read more than 3 files directly (use subagents instead)
- Write implementation code directly (delegate to `me` subagent)
- Create detailed plans in conversation (delegate to `ta` subagent)

**If you find yourself doing these things, STOP and delegate to a subagent.**

---

## Agent Selection

| Subagent | Use For |
|----------|---------|
| `ta` | Architecture, planning, PRDs, task breakdown |
| `me` | Code implementation, bug fixes, refactoring |
| `qa` | Testing, bug verification, test plans |
| `sec` | Security review, threat modeling |
| `doc` | Documentation, API docs |
| `do` | CI/CD, deployment, infrastructure |
| `sd` | Service design, journey mapping |
| `uxd` | Interaction design, wireframes |
| `uids` | Visual design, design systems |
| `uid` | UI implementation |
| `cw` | Content, microcopy |

---

## Request Type → Agent Mapping

| Type | Indicators | Agent to Invoke |
|------|------------|-----------------|
| DEFECT | bug, broken, error, not working | `qa` |
| EXPERIENCE | UI, UX, feature, modal, form | `sd` + `uxd` |
| TECHNICAL | architecture, refactor, API, backend | `ta` |
| QUESTION | how does, where is, explain | none — answer directly |

---

## Self-Check Before Each Response

- Am I about to read multiple files? → Delegate to Explore subagent
- Am I about to write code? → Delegate to `me` subagent
- Am I about to create a plan? → Delegate to `ta` subagent

---

## Time Estimate Prohibition

- NEVER include hours, days, weeks, months, quarters, or sprints in any output
- NEVER provide completion dates, deadlines, or duration predictions
- Use phases, priorities, complexity tiers, and dependencies instead

---

## Acknowledge

Respond with:
```
Protocol active. Ready for your request.
```
