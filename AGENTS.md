# Agent Instructions

## Development Workflow (Strict TDD)
- Follow strict TDD: write failing tests first, then implement, then refactor.
- Develop locally; use the project `.venv` for Python commands when available.
- For each worktree, create a dedicated `.venv` when needed and delete it during cleanup.
- Integration and E2E tests must use real services and real data (no mocks).
- Unit tests may use mocks when appropriate.
- When fixing errors: always do a root cause analysis first and fix the root cause, if you are not able to fix the root cause, you need approval by user before proceeding.

## Story Quality Gate
- Before development, ensure the user story is absolutely clear.
- Ensure acceptance criteria are excellent and complete.
- Ensure test coverage plan is excellent (unit + integration + e2e).
- Begin implementation only after the above is completed and explicitly approved by the user.

## E2E Coverage Expansion
- When adding a new user story to development, extend existing E2E coverage or create a new E2E test.
- Prioritize broad, realistic tests to uncover architectural or logical flaws.

## Branching & CI Workflow
- For each new story, create a new git worktree and a dedicated feature branch before starting work.
- Pull the latest `main` before starting work on a feature branch.
- Ensure CI is configured to run automatically on push/PR for the feature branch.
- After implementation and local unit tests pass, push the branch and open a PR so CI runs on GitHub.
- Ensure the PR CI executes the full test suite before merge.
- Before merging to main, the full test suite must pass.

## Self-Review Gate
- Provide a short self-review checklist before merge.
- Include: edge cases handled, error handling verified, real services/data used for integration/E2E, is the test coverage excellent?
