---
name: security-review
description: Review a code diff for common vulnerabilities — injection, authz bypass, secret leakage, dependency risks.
license: MIT

flock:
  # Forces runtime mode for this skill, even if caller doesn't set runtime=True.
  # Rationale: this skill's body is 8000+ tokens and shouldn't be compiled into
  # every consumer's signature. Always lazy-load.
  mode: tool
---

## When to use

Given a code diff (unified diff format), identify potential security issues.
Prioritize:
1. User-input handling without validation / escaping
2. Authz checks that appear to be bypassed or missing
3. Hardcoded secrets / credentials / API keys
4. Dependencies with known CVEs (check lockfile changes)
5. SQL/NoSQL/command injection patterns

## How to review

For each hunk:
- Classify hunk type: new endpoint | auth change | data-mutation | dependency | config
- Apply hunk-type-specific checklist (see references/)
- Rate severity: critical | high | medium | low
- Suggest specific mitigation with code example

## References

- `references/owasp-top-10-2025.md` — current OWASP Top 10 with Rails/Python-specific patterns
- `references/secrets-patterns.md` — regex patterns for common secret types
- `references/authz-bypass-patterns.md` — common Rails/Django auth misuse

## Out of scope

This skill does not:
- Run SAST tools (use the `sast-scanner` skill for that)
- Check license compliance (use `license-audit` skill)
- Review infrastructure/IaC (use `iac-review` skill)
