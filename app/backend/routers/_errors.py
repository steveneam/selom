"""Run-path error taxonomy — one honest, actionable shape for every failure a run surfaces.

Three inconsistent styles used to reach the FE from a run: the engine degrades to ``None``
(fail-soft, ``_run._inspect_for_run``), the router raised an ad-hoc ``HTTPException`` (sometimes a
structured ``{error, message, …}`` dict, sometimes a bare string), and a skill runner raised
``ValueError`` — surfaced as a *bare-string* 400. So a fixable data mismatch ("missing required
columns …") reached a stranger as the generic "Couldn't run this skill … Please try again.", while a
gate error came through self-framed. This module gives all of them ONE envelope, mirroring the
QC-flag shape (``engine/qc.py`` :class:`~engine.models.QCFlag`: ``severity`` / ``code`` / ``message``
/ ``fix``) so the FE reads a run error exactly the way it reads a data-quality flag.

Category is the ``severity`` peer — *what kind* of failure, so the FE frames it right:

``bad_input``
    The user's data / params are the problem; they can fix it (HTTP 400 / 422).
``unsupported``
    The request names something we don't offer or can't serve yet — an unknown skill / dataset, an
    un-materialized upload (HTTP 404 / 409).
``internal``
    Our side failed — a timeout or an unexpected error; not the user's fault (HTTP 5xx / 504).

Every :class:`RunError` serializes to ``detail = {error, category, message, fix, **context}``.
``error`` (the machine code) and any structured ``context`` keys (``qc`` / ``routing`` / ``missing``
/ ``errors`` / …) are preserved **verbatim** so existing FE branches and gate contracts keep working;
``category`` + ``fix`` are the additive taxonomy fields. Raise the constructors so each category stays
paired with its default HTTP status.
"""

from __future__ import annotations

from fastapi import HTTPException

BAD_INPUT = "bad_input"       # the user's data / params — a fixable 400 / 422
UNSUPPORTED = "unsupported"   # unknown / not-yet-servable — 404 / 409
INTERNAL = "internal"         # our fault — timeout / unexpected — 5xx
CATEGORIES = (BAD_INPUT, UNSUPPORTED, INTERNAL)


class RunError(HTTPException):
    """A run-path failure in the one canonical shape. It *is* an :class:`~fastapi.HTTPException`, so
    ``raise RunError.bad_input(...)`` needs no custom handler — FastAPI serializes ``self.detail`` =
    the envelope. Use :meth:`bad_input` / :meth:`unsupported` / :meth:`internal` so the category and
    its default status stay paired; pass ``status_code`` to override (a bad-input *gate* is 422,
    an un-materialized upload is 409, a timeout is 504)."""

    def __init__(self, *, status_code: int, category: str, code: str, message: str,
                 fix: str = "", context: dict | None = None):
        self.category = category
        self.code = code
        self.message = message
        self.fix = fix
        # `error` == the machine code (unchanged from the pre-taxonomy gate dicts so the FE's
        # data_check_failed branch + every `detail["error"]` test still resolve); category + fix are
        # additive. Structured context (qc / routing / missing / errors / violations / …) rides along
        # verbatim so nothing a gate used to carry is lost.
        detail: dict = {"error": code, "category": category, "message": message, "fix": fix}
        if context:
            detail.update(context)
        super().__init__(status_code=status_code, detail=detail)

    @classmethod
    def bad_input(cls, code: str, message: str, *, fix: str = "", status_code: int = 400,
                  **context) -> "RunError":
        """The user's data / params are wrong — they can fix it. 400 by default; a pre-run *gate*
        (QC block, data-contract, frame-schema) passes ``status_code=422``."""
        return cls(status_code=status_code, category=BAD_INPUT, code=code, message=message,
                   fix=fix, context=context)

    @classmethod
    def unsupported(cls, code: str, message: str, *, fix: str = "", status_code: int = 404,
                    **context) -> "RunError":
        """The request names something we don't offer / can't serve yet. 404 by default; an upload
        whose bytes never landed passes ``status_code=409`` ("re-upload to materialize")."""
        return cls(status_code=status_code, category=UNSUPPORTED, code=code, message=message,
                   fix=fix, context=context)

    @classmethod
    def internal(cls, code: str, message: str, *, fix: str = "", status_code: int = 500,
                 **context) -> "RunError":
        """Our side failed — not the user's fault. 500 by default; an exec timeout passes
        ``status_code=504``."""
        return cls(status_code=status_code, category=INTERNAL, code=code, message=message,
                   fix=fix, context=context)


# --- shared shapes (used at >1 raise site — one home so they can't drift) ---------------------

def unknown_skill(skill_id: str) -> RunError:
    """An unknown skill id — the same 404 whether a run, a job, or a param-recommend asked for it."""
    return RunError.unsupported(
        "unknown_skill", f"No skill named {skill_id!r}.",
        fix="Pick a skill from the catalog (GET /skills).")


def param_out_of_range(range_errors: list[str]) -> RunError:
    """An out-of-range knob — the same 400 on /run and on the /jobs enqueue paths. `range_errors`
    (from ``validate_param_ranges``) names each offending param + its bound, carried as context."""
    return RunError.bad_input(
        "param_out_of_range", "One or more parameters are outside their allowed range.",
        fix="Adjust the flagged parameter(s) to within the allowed range shown.",
        errors=range_errors)
