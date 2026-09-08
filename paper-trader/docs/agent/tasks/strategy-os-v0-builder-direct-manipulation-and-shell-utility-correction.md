---
{
  "id": "strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction",
  "lineage_id": "strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction",
  "programme_stage": "strategy-os-v0-monitoring-signals-review",
  "phase": "v0",
  "status": "accepted",
  "kind": "important_desktop_builder_interaction_and_shell_utility_correction",
  "goal": "Make the V2 builder behave like a direct-manipulation desktop editor: Delete and Backspace stage removal of the selected node, dragged nodes follow the pointer continuously and stage only their final layout, the collapsible shell sidebar provides useful real navigation and workspace context without advertising unfinished products, and a signed-in user cannot enter Strategies until the enabled Zerodha data onboarding has a stored browser session.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "The two builder defects and missing first-sign-in provider gate reproduce RED; keyboard deletion, continuous drag and final-only layout staging are green; editable/modal/modified-key safety and focus restoration pass; the sidebar exposes only real V0 destinations, current workspace context, refresh and collapse behavior; the authenticated account strip is compact; an unconfigured or reauthentication-required Zerodha state redirects Strategies to provider onboarding while a stored session does not; focused/subsystem tests, typecheck/build, browser verification, three isolated ablations, protected hashes and architecture all pass."},
  "authorization_resolution": {"status": "EXPLICIT_OWNER_FRONTEND_DIRECTION", "evidence": "The owner reported that Delete does not remove selected nodes, dragging snaps instead of following the cursor, and the sidebar is useless, and asked for these frontend behaviors to be fixed.", "desktop_first": true, "mobile_optimization": false},
  "risk_tags": ["important", "frontend", "builder", "keyboard", "pointer", "accessibility", "presentation-state", "shell", "desktop", "provider-onboarding"],
  "required_skills": ["strategyos-repo-orientation", "executing-strategy-os-slices", "ui-ux-pro-max", "accessibility-audit", "running-strategy-os-safely"],
  "depends_on": ["strategy-os-v0-frontend-product-acceptance-recovery", "strategy-os-v0-v2-editor-private-restore-structural-correction", "strategy-os-v0-data-provider-key-onboarding-local-foundation"],
  "required_docs": [
    {"path": "paper-trader/docs/agent/CURRENT.md", "sections": ["v0_canonical_research_spine", "v0_provider_private_conformance_readiness"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy.md", "sections": ["final_review", "owner_gates", "nonclaims"]},
    {"path": ".agent/runs/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction/owner/orientation.log", "sections": ["checkout", "frontend dirty-tree and file hashes"]}
  ],
  "allowed_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/research/StrategyBuilderWorkspace.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/research/StrategyBuilderWorkspace.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/research/research-workstation.css",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product/routes.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product/routes.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/.agent/runs/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction",
    "paper-trader/docs/agent/tasks/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction.md",
    ".agent/runs/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction.md",
    ".agent/runs/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction"
  ],
  "external_review_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/research/StrategyBuilderWorkspace.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/research/StrategyBuilderWorkspace.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/research/research-workstation.css",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product/routes.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product/routes.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx"
    ,"/Users/priyanshusaraf/dev/strategy-os-frontend/.agent/runs/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction"
  ],
  "protected_paths": [
    "paper-trader/backend",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/scripts/deploy.sh",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.tsx"
  ],
  "scope": [
    "Use the existing staged remove_node command for keyboard deletion. Delete and Backspace act only when a graph node is selected, no help dialog is open, the event is not composing/repeated/modified, and no editable control appears in the target or composed path.",
    "Keep React Flow built-in deletion disabled so keyboard removal cannot bypass semantic staging. After removal, select and focus the nearest remaining node alternative, or focus the builder heading if none remains.",
    "Update presentation position continuously during onNodeDrag so the controlled node follows the pointer. Do not add grid snapping or transitions. OnNodeDragStop adds exactly one set_position layout command; drag motion adds no semantic command and no intermediate persisted command.",
    "Keep coordinates out of ordinary user copy. Add a concise visible Delete shortcut hint to the existing removal control and keep the existing non-pointer positioning alternative.",
    "Make the shell sidebar useful with only real routes: Strategies, Account and Data provider when enabled. Include compact current project/strategy context where known, move refresh into sidebar utility, preserve provider status and keep the sidebar collapsible with accessible labels and visible focus.",
    "Reduce the inherited authenticated-account strip to a compact menu through CSS only. Do not move auth authority, session actions or password inputs and do not expose secrets.",
    "When the server publishes Zerodha data onboarding, gate only the Strategies route on the owner-scoped connection status. Route CONNECTION_REQUIRED, APP_KEYS_REQUIRED, REAUTH_REQUIRED and REVOKED to /account/provider; allow SESSION_PRESENT_UNVERIFIED; fail closed on UNAVAILABLE or an unverifiable response. Keep Account and Data provider reachable so the user can recover.",
    "Do not add Alerts, Paper, Admin, deployment or other unavailable navigation. Do not change backend, API, strategy identity, semantic commands, schema, provider, money or deployment behavior."
  ],
  "acceptance": [
    "A pointer-selected node is removed from the working graph by unmodified Delete or Backspace, its connected edges disappear through the existing projection, the staged graph count increments once, and no server call occurs until Apply draft.",
    "Delete and Backspace remain untouched inside input, textarea, select, contenteditable, role=textbox and their composed descendants; modifiers, repeats, composition and an open help dialog do not remove a node.",
    "A dragged node position changes on at least two onNodeDrag frames before pointer release, matches each pointer position without quantization, and creates no staged layout command until onNodeDragStop, which creates one final command.",
    "The shell sidebar has real Strategies, Account and Data provider destinations, workspace context when available, Refresh and Collapse controls. The collapsed rail retains icons, accessible names, current-page state and expansion.",
    "The signed-in account strip no longer occupies a large empty horizontal block. Its account controls remain reachable, labelled, keyboard-operable and unchanged in authority.",
    "A first authenticated visit to Strategies redirects to Zerodha onboarding until a provider connection, encrypted app keys and browser session exist. A stored session allows subsequent visits without re-entering app keys; REAUTH_REQUIRED redirects again. No secret is put in localStorage, sessionStorage, a URL or user-visible status.",
    "Focused builder/shell/auth tests, frontend typecheck and build pass. The live isolated 5187 preview demonstrates Delete, continuous drag and sidebar collapse on the actual product route without console errors.",
    "ABL-DELETE-STAGING removes the custom delete handler and makes the exact keyboard regression RED. ABL-DRAG-FRAMES removes continuous drag updates and makes the exact frame test RED. ABL-PROVIDER-GATE bypasses the provider gate and makes the first-sign-in routing test RED. Exact source bytes restore and the same tests return GREEN."
  ],
  "test_plan": [
    "First add failing component tests with the React Flow mock exposing onNodeClick, onNodeDrag, onNodeDragStop and onPaneClick. Reproduce absent Delete behavior and final-only snapping.",
    "Add shell tests for provider navigation, context, refresh, collapse, accessible names and no unavailable routes. Add AuthGate layout assertions only where DOM structure is relevant; do not turn CSS appearance into a weak text assertion.",
    "Run StrategyBuilderWorkspace, PrecisionShell, product routes and AuthGate tests; then full frontend tests, typecheck and build.",
    "Run three isolated source ablations in a temporary copy and restore exact hashes. Verify the live HTTPS preview using mock/Paper/unarmed temporary state."
  ],
  "risk_classification": {"tier": "Important", "reason": "The change affects destructive keyboard interaction, controlled graph motion, focus, global navigation and post-authentication provider onboarding, but does not change server authority, credential storage or executable strategy identity."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {
    "required": false,
    "assignment_id": "v0_builder_direct_manipulation_shell_utility_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction/review-package.json",
    "review_paths": [
      "paper-trader/docs/agent/tasks/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction.md",
      ".agent/runs/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction"
    ],
    "exclude_paths": [
      "paper-trader/backend",
      "paper-trader/frontend",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction/report.md",
    "verdicts": ["INTERACTION", "ACCESSIBILITY", "VISUAL_QA"],
    "max_rechecks": 0
  },
  "owner_gates": [
    "Frontend authority is limited to the owner-reported desktop defects. No backend, API, schema, provider, monitoring worker, live, money or deployment change.",
    "Do not invent destinations for unfinished Alerts, Paper, Admin, deployment or future releases.",
    "Preserve all inherited frontend bytes outside exact paths and do not reset, clean, stash, rebase, stage, commit or push."
  ],
  "stop_conditions": [
    "Correct deletion requires bypassing staged V2 mutation commands or changing backend semantics.",
    "Smooth motion requires executable position identity, semantic commands during drag or a dependency change.",
    "Useful sidebar navigation requires advertising an unavailable route or changing account/session authority.",
    "A protected path, schema, backend, live, money or deployment edit is required."
  ],
  "deployment_impact": {"classification": "frontend-only interaction and layout correction", "schema_change": false, "dependency_change": false, "configuration_change": false, "runtime_wiring": false, "locally_runnable": true, "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No backend/editor authority, provider readiness, alert/Paper/admin frontend, mobile optimization, release deployability, deployment or V0 completion follows from this correction."]
}
---

# V0 builder direct manipulation and shell utility correction

Fix the actual desktop builder and shell shown in the authenticated V0 preview.
Keyboard deletion uses the existing staged semantic command. Pointer motion stays
presentation-only. The sidebar exposes only real product destinations.
