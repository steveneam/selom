# Selom — On Hold  →  MOVED

**This register was folded into `docs/on-hold/README.md` on 2026-07-25 (plan `OH-15`).**
That file is now the single home for every parked item. Do not add rows here.

## Why it moved

Two on-hold registers existed with overlapping rows (Redis, deploy image, BAM), which breaks the
Ratchet's one-durable-home rule: two homes means one of them is silently wrong, and there is no way
to tell which. Everything here was migrated with its reason **restated**, not copied.

## Why its premise was stale

This file gated work behind *"ask before any Docker/WSL work"* — a **Windows-era** constraint. The
owner cleared Docker on this Linux box on 2026-07-23 (Engine v29.6 + Compose, stood up for Nango),
and a Redis has been running on `:6380` since. So **no row here was actually infra-blocked any
more**, and several had never been: their real reason was off-thesis breadth or an open product
question, wearing an infra excuse. [[ask-before-docker-wsl]]

## Where its five rows went

| Was | Now |
|---|---|
| 1 · Kaleido journal export | **DONE 2026-06-15** — its gate had been wrong from the start (Kaleido v1 needs no container at runtime). Recorded under *Graduated*. |
| 2 · arq Redis job-status store | **UNPARKED 2026-07-25** at the Phase 0 founder gate — executes locked decision #6. Recorded under *Graduated*; queued for the sprint after the 3-lane partition. |
| 3 · OmicVerse isolated worker | Still parked, **reason restated**: GPL-3.0 licence + off-thesis breadth. The `pandas<3` isolation need is real; Docker was never the blocker. |
| 4 · Deploy image | Still parked, **reason restated**: no longer infra-gated, and it now overlaps the public-backend-on-syd2 work — tracked there, once. |
| 5 · Community skill sandbox | Still parked, **reason restated**: v2 scope. The Skill Foundry community tier does not exist yet. |

_Superseded 2026-07-25. Original filed 2026-06-13, owner-directed._
