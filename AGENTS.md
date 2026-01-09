# Agent Instructions

## Development Workflow (Strict TDD)
- Follow strict TDD: write failing tests first, then implement, then refactor.
- Provide tests for review and approval before implementing production code.
- Develop locally; use the project `.venv` for Python commands when available.
- For each worktree, create a dedicated `.venv` when needed and delete it during cleanup.
- Integration and E2E tests must use real services and real data (no mocks).
- Unit tests may use mocks when appropriate.
- When fixing errors: always do a root cause analysis first and fix the root cause, if you are not able to fix the root cause, you need approval by user before proceeding.

## Story Quality Gate
- Every change must be documented as a user story, change request, or hotfix. If no existing doc covers the work, create a new one first in github issues.
- Github issues is the source of truth for all stories, change requests, and hotfixes
- Before development, ensure the user story is absolutely clear.
- Ensure acceptance criteria are excellent and complete.
- Ensure test coverage plan is excellent (unit + integration + e2e).
- When writing GitHub issues, use proper Markdown with real newlines (no escaped `\\n`).
- Quality Gate #1: begin test or implementation work only after the above is completed and explicitly approved by the user.

## Test Quality Gate
- Quality Gate #2: create failing tests before implementation and get user approval on the tests before writing production code.

## E2E Coverage Expansion
- When adding a new user story to development, extend existing E2E coverage or create a new E2E test.
- Prioritize broad, realistic tests to uncover architectural or logical flaws.

## Branching & CI Workflow
- Quality Gate #2.5: run `black` and `ruff` locally and fix issues before pushing code to CI.
- Quality Gate #3: never push directly to main. Always use a new worktree and feature branch, commit locally, push the branch, and open a PR so CI runs on GitHub.
- For each new story, create a new git worktree and a dedicated feature branch before starting work.
- Pull the latest `main` before starting work on a feature branch, and re-sync `main` before opening a PR.
- Ensure CI is configured to run automatically on push/PR for the feature branch.
- After implementation and local unit tests pass, push the branch and open a PR so CI runs on GitHub.
- Ensure the PR CI executes the full test suite before merge.
- Before merging to main, the full test suite must pass.

## Dev/Staging/Prod Workflow
- Implement code and validate in `.venv` first (unit + integration tests as applicable).
- Validate in the dev compose environment with real services (`make env-dev-up`).
- During implementation/testing, run only the new or changed E2E tests locally against dev Docker; run the full E2E suite in GitHub Actions/CI.
- Before running validations, confirm preconditions: services are healthy, env vars are correct, and the running image matches the branch/commit under test.
- When changes affect runtime deps or container startup, run a container-level smoke check (import or `--help` for key CLIs).
- Push to GitHub and rely on CI for the full test suite.
- Deploy the CI-built image tag to staging and run E2E tests there.
- Promote the same image tag to prod after staging passes.

## Self-Review Gate
- Provide a short self-review checklist before merge.
- Include: edge cases handled, error handling verified, real services/data used for integration/E2E, is the test coverage excellent?
