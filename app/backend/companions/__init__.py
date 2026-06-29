"""Figure-companion artifact builders (repo-structure plan §3B).

The four builders that run together in ``_execute_skill_run`` / ``jobs.queue`` so every
figure ships with its methods text, legend, provenance bundle, and guardrail warnings:

  methods     — auto-Methods prose per skill + canonical citations
  legends     — figure-legend text
  provenance  — environment / version / input-hash bundle
  guardrails  — pre/post-run advisory warnings (FDR, double-normalization, batch, …)

Import the concrete submodule (no re-export hub): ``from companions import methods``.
``export.py`` stays flat — it is figure-IO, not a companion artifact.
"""
