# Public Repository Security Audit

Last updated: 2026-07-21 (Asia/Bangkok)

This document is the source of truth for the audit performed when
`nattakit2580/Agent-Invest` changed from private to public. It deliberately does
not contain the values of any email address, Telegram identifier, session URL,
or suspected secret.

## Executive summary

No authentication credential was found in the public repository or its
reachable Git history. Specifically, the audit found no API key, Telegram bot
token, password, private key, real `.env` file, database, log, or generated
customer report.

The history does expose non-secret personal/operational metadata:

- Two Gmail commit-author addresses.
- One production-style Telegram chat/channel identifier in one commit message
  (the same logical identifier appears with positive and negative signs).
- One Claude session URL repeated across 21 commit messages.

These items do not grant application access by themselves, but the repository
owner must decide whether their public visibility is acceptable. Do not state
that the repository contains "no exposed information"; the accurate statement
is "no credentials were found, but non-secret metadata is public."

## Remote state captured

- Repository: `https://github.com/nattakit2580/Agent-Invest`
- Visibility: public (confirmed through the GitHub API).
- Default branch: `main`.
- Public `main` at the end of the audit: `962a0ee`.
- Public branch heads returned by `git ls-remote`: 15.
- Unique commits reachable from a fresh clone of all public remote refs: 88.
- Issues and pull requests audited: 0.
- Issue/PR comments audited: 0.
- Releases audited: 0.

Remote state changed during the audit: `main` moved from `0e48f01` to
`962a0ee`. Always re-query the remote before acting. The local dirty readiness
work is still based on `0e48f01`; integrate the new remote commit carefully and
do not overwrite the existing worktree.

## Audit methods

The following independent checks were used:

1. GitHub repository metadata through the connected GitHub app.
2. `git ls-remote` to enumerate all public branch and tag refs.
3. A fresh public clone in `C:\tmp`, followed by an explicit fetch of every
   public branch and tag.
4. Gitleaks v8.30.1 over `--all` Git history with 100% output redaction. The
   official Windows x64 release archive and checksum file were downloaded from
   the Gitleaks GitHub release and the SHA-256 was verified before execution.
5. Independent pattern checks for common provider tokens, private-key headers,
   Telegram bot-token formats, sensitive environment assignments, email
   addresses, Thai phone/ID patterns, Telegram chat identifiers, and Claude
   session URLs.
6. Historical filename review for real `.env` files, key/certificate files,
   databases, logs, spreadsheets, reports, screenshots, and runtime artifacts.
7. Commit-author and commit-message metadata review with values masked.
8. GitHub API review of issue, pull-request, comment, and release text.
9. GitHub Secret Scanning alerts API query.

Temporary clones, the Gitleaks executable, checksum file, and redacted reports
were removed from `C:\tmp` after the audit.

## Results

### Credential and file exposure

- High-confidence API token/private-key patterns: none.
- Non-placeholder sensitive environment assignments: none.
- Historically tracked sensitive filenames: none.
- Secret patterns in GitHub issues/PRs/comments/releases: none.
- Current documentation contains two Telegram IDs that match the numeric shape,
  but both are obvious sequential sample values rather than production IDs.

### Gitleaks findings

Gitleaks produced four findings. Each was inspected with the detected span
redacted before context was displayed. All four are false positives:

- `6fab236`, `backend/agents/technical_agent.py:10`: prose about JSON keys/enums.
- `5460a6c`, `backend/agents/technical_agent.py:12`: prose about JSON keys/enums.
- `cbc5304`, `backend/agents/technical_agent.py:12`: prose about JSON keys/enums.
- `d83895a`, `docs/telegram-bot.md:66`: the word `curl` in an instruction.

Do not add broad allow-list rules for these findings without reviewing the exact
Gitleaks fingerprints. A narrow `.gitleaksignore` may be added later if Gitleaks
is made part of CI.

### Public non-secret metadata

- Two non-noreply Gmail author addresses are present in Git commit metadata.
- One commit message records a production Telegram chat/channel identifier.
  A chat ID alone is not a bot credential and cannot send messages without a
  valid bot token; no bot token was found.
- One Claude session URL appears in 21 commit messages. The URL was not opened
  during the audit. Treat it as potentially private metadata until the owner
  verifies its access behavior or revokes/removes the associated session.
- One 13-digit value in commit messages was verified not to satisfy the Thai
  national-ID checksum; it was the Telegram identifier described above.
- No Thai phone-number pattern was found in commit messages.

### GitHub security controls

The GitHub Secret Scanning alerts API returned that secret scanning was disabled
for this repository at audit time. Enable Secret Scanning/Secret Protection and
Push Protection in repository security settings, then query alerts again.

## Residual risk and limitations

- Automated scanners cannot prove that arbitrary, unstructured text never
  contains confidential business context.
- The scan covers public Git refs available during the audit. A later push,
  branch, tag, issue, release, or uploaded artifact requires a new scan.
- Repository settings, deployment-provider secrets, Telegram settings, and
  OpenRouter account data are outside Git content and were not read.
- Making a repository private or rewriting history cannot guarantee deletion
  from clones, forks, caches, mirrors, or earlier downloads.
- Author emails and the operational metadata above are already public. History
  rewriting is disruptive, changes commit SHAs, and must cover all public refs.
- The local readiness changes are not yet on public `main`, so their successful
  local dependency/build audits do not describe the currently published code.

## Required follow-up

1. Enable GitHub Secret Scanning/Secret Protection and Push Protection.
2. Decide whether the two author emails, Telegram identifier, and Claude session
   URL are acceptable public metadata.
3. If the Claude session could expose private content, revoke/delete it first.
4. If metadata removal is required, temporarily restrict visibility and plan a
   coordinated history rewrite for every public branch. Do not force-push or
   delete refs without explicit owner authorization and a recovery plan.
5. Configure future Git commits to use the GitHub-provided noreply address.
6. Integrate remote `962a0ee` into the dirty local readiness work without
   discarding either side.
7. Choose and add a repository license.
8. Push the readiness work, wait for CI, then rerun this public audit against a
   fresh clone of the exact published commit.
9. Consider adding Gitleaks to CI and pre-commit checks with narrowly reviewed
   false-positive fingerprints.

## Rules for the next agent

- Never print a detected secret or complete personal identifier in tool output,
  chat, documentation, an issue, or a commit message.
- Report findings by rule, file, line, and short commit only. Redact the matched
  span before inspecting context.
- Verify the checksum of any downloaded security scanner before execution.
- Use a clean clone outside OneDrive and scan all remote refs, not just `main`.
- Re-check remote refs immediately before and after an audit because the remote
  may change during the work.
- Update this document and `HANDOFF.md` with the published commit, scan result,
  security-control status, and any new residual risk.

