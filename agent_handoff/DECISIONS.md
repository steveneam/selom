# Selom — DECISIONS (Locked)

> Binding decisions for the Selom build. Agents treat these as authoritative.
> Supersede by append (with a new stamp), never silently overwrite. Deep ADRs
> live in the research vault; this file is the build-side quick reference.

_Last updated: 2026-06-10 20:46 +10:00_

| # | Decision | Rationale | Source |
|---|---|---|---|
| 1 | **Stack = Python (FastAPI) backend + Next.js frontend.** R is **validation-only** — never on the hot path; used to produce golden reference outputs the Python skills are tested against. | Single production language (Python) for skill runners; R kept as a correctness oracle only. | ADR 0002 |
| 2 | **The build repo lives at `D:/selom`** — separate from the research vault. | Code stays in `D:/selom`; the vault holds research + operational mirrors only. Clean separation of build vs. knowledge. | Project layout |
| 3 | **Commercial / licensing gates are intentionally DEFERRED** for build-for-self. | Owner directive: build the product first, apply commercial/licensing gates before launch. Gates never block in-lane build work. See `RISKS.md` #6 (AGPL) for the one item that must clear the pre-launch gate. | Owner directive |
| 4 | **Git staging is explicit** — never `git add -A` after the initial scaffold commit. | Disjoint two-agent lanes mean blanket staging risks committing the other agent's in-flight work. Stage named paths only. | Coordination protocol |

## Notes

- Decision #1 (Python + Next.js, R validation-only) defines the lane split:
  Codex owns Python `app/backend`; Claude owns Next.js `app/frontend`.
- Decision #3 is the policy behind `RISKS.md` #6: deferred does not mean
  cancelled — the AGPL / commercial gate must be cleared before any external user.
- Decision #4 binds both agents: after the scaffold commit, every commit stages
  explicit paths so the disjoint lanes never cross-contaminate.
