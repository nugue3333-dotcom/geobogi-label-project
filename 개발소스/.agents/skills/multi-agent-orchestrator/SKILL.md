---
name: multi-agent-orchestrator
description: Use when work in this project should be split across multiple Codex agents for faster delivery, parallel investigation, implementation, UI review, verification, release checks, or documentation.
---

# Multi-Agent Orchestrator

Use this skill when a task in this project is large enough to benefit from multiple Codex app sub-agents that review one another through the main Codex conversation.

## Routing

1. Read the root `AGENTS.md`.
2. Read `.agents/team.json`.
3. Use Codex app internal sub-agents by default:
   - Keep the current Codex app conversation as the lead-integrator thread.
   - Spawn focused app sub-agents for diagnosis, implementation side work, and verification.
   - Do not launch nested `codex.exe` from PowerShell unless the user explicitly requests legacy CLI automation.
4. Choose the smallest useful set of agents:
   - `project-mapper` for read-only structure and command discovery.
   - `feature-worker` for assigned implementation files.
   - `ui-ux-worker` for assigned UI files.
   - `qa-release-verifier` for tests, builds, dry-runs, and customer-facing artifact checks.
   - `docs-ops` for runbooks and deployment notes.
5. Keep the main agent as `lead-integrator`.
6. Split write scopes so two agents do not edit the same file at the same time.

## App Usage

Ask in the Codex app:

```text
Codex 앱 멀티에이전트로 [작업 설명] 진행해
```

The main conversation stays responsible for integration, conflict resolution, final validation, and the user-facing report.

## Legacy Script Usage

These scripts are retained for prompt package generation and explicit CLI automation. They are not the default path for real edits.

Create a council transcript and prompts only:

```powershell
.\scripts\start_agent_council.ps1 -Task "작업 설명"
```

Create independent role prompts only:

```powershell
.\scripts\start_multi_agents.ps1 -Task "작업 설명"
```

`-Launch` starts nested Codex CLI processes from the terminal and is legacy-only. Prefer Codex app internal sub-agents for real implementation work.

## Completion Checklist

- The lead integrator reviews results before final reporting.
- Validation results are separated into success, failure, and not-run items.
- No physical printer output, live message send, real-account action, or production server change is performed unless the user explicitly requested it.
- If customer-facing EXEs are affected, tests, PyInstaller build, copy to `고객용_실행폴더`, hash verification, and real EXE smoke checks are all completed.
- Customer preflight verifies `out\customer_preflight_report.txt` and `out\customer_support_package.zip` when customer deployment is in scope.
- Print checks use dry-run by default and inspect `print_queue.xlsx`, `print_log.xlsx`, `last_run.log`, and `out\` artifacts.
- Do not treat printer-send success as physical label-output success.
- Confirm the default template remains intentionally blank with `"elements": []`.
