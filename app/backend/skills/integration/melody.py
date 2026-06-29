"""Selom Melody — clean-room batch integration for single-cell data (proprietary).

**Melody** is Selom's clean-room implementation of the **Harmony** integration *method*
(Korsunsky et al., "Fast, sensitive and accurate integration of single-cell data with
Harmony", *Nature Methods* 16:1289-1296, 2019 — doi:10.1038/s41592-019-0619-0). The method
is theirs and is cited; the *code* here is ours, written purely from the published Online
Methods (Algorithms 1-3, eqs 3-14) in ``numpy`` — it does **not** copy ``harmonypy`` or the
R ``harmony`` package, both of which are GPL-3.0 (only code expression is copyrightable; a
published algorithm is not). "Melody" is the Selom name so our proprietary implementation
is never confused with the GPL "Harmony" packages. This module replaces
``scanpy.external.pp.harmony_integrate`` (which wraps GPL ``harmonypy``) on the
``integration`` skill's shipped path, removing the GPL dependency entirely; ``harmonypy`` is
kept installed only as a validation oracle (see ``tests`` / the s29 dogfood).

The algorithm iterates two steps over a PCA embedding ``Z`` (N cells x d PCs) until the
objective converges:

  1. **Maximum-diversity soft clustering** (Algorithm 2) — a soft, spherical (cosine)
     k-means into K clusters whose objective adds, to the usual distance + entropy terms,
     a diversity penalty that pushes every cluster toward a batch-balanced mix. The soft
     assignment update for cell ``i`` to cluster ``k`` (eq 8, with the +1 smoothing of
     §2.6.3) is::

         R[k,i]  ∝  exp(-2 (1 - Yk·Zi) / sigma) * ((1 + Exp[k,b]) / (1 + Obs[k,b]))^theta_b

     where ``b`` is cell ``i``'s batch and, for cluster ``k`` x batch ``b``, ``Obs`` is the
     observed cluster/batch co-occurrence (``R @ phi.T``) and ``Exp`` the value expected
     under cluster/batch independence (``rowsum(R) ⊗ Pr_batch``). Columns of ``R`` are
     renormalised to sum to 1.

  2. **Mixture-of-experts linear correction** (Algorithm 3) — for each cluster, a ridge
     regression (penalty ``lamb`` on the batch columns, intercept unpenalised) of the
     **original** ``Z`` on the augmented one-hot batch design ``phi* = [1; phi]``, weighted
     by that cluster's soft membership. Only the batch coefficients are subtracted (the
     intercept — cell-type-level signal — is kept). Correction always regresses the
     original ``Z`` (never the running corrected embedding) so the transform stays a single
     linear model of the input, which the authors found avoids over-correction (§1.1).

An optional ``harmony2=True`` mode (default off — the shipped/validated path is the 2019
method) folds in the two clean-room **Harmony2** (Patikas et al., bioRxiv 2026) quality
improvements — a stabilized scale-invariant diversity penalty and dynamic per-batch ridge
(``lambda_hat = alpha * E``) — both aimed at avoiding over-integration in large,
heterogeneous data. See ``melody`` / ``docs/records/harmony2-scope/scope.md``.

Determinism: with a fixed ``random_state`` the KMeans initialisation and the block update
order are both seeded, so ``melody`` is bit-stable across runs. Pure
``numpy`` + ``scikit-learn`` (KMeans init) — no C/C++/CMake, no ``harmonypy``, no
``scanpy`` import. Validation is by the batch-mixing METRIC vs. the harmonypy oracle, not a
pixel-identical embedding (the method is stochastic in its init).
"""

import numpy as np

# Standard Harmony-method defaults (Korsunsky 2019 Online Methods + the universally documented
# package defaults). sigma/lambda/epsilons are not printed as numbers in the Methods; these
# are the established values, matched to the harmonypy oracle so validation is apples-to-apples.
_SIGMA = 0.1          # entropy weight (cluster fuzziness)
_LAMBDA = 1.0         # ridge penalty on batch coefficients (intercept unpenalised)
_ALPHA = 0.2          # Harmony2 dynamic-lambda scale: lambda_hat_kb = alpha * E_kb (§"Dynamic lambda")
_MAX_ITER_CLUSTER = 20
_EPS_CLUSTER = 1e-5
_EPS_HARMONY = 1e-4
_TINY = 1e-12
_RIDGE_FLOOR = 1e-8   # floor on the dynamic ridge so an empty (cluster,batch) cell stays invertible


def melody(
    Z,
    batch,
    *,
    theta: float = 2.0,
    max_iter_harmony: int = 10,
    max_iter_cluster: int = _MAX_ITER_CLUSTER,
    nclust: int | None = None,
    sigma: float = _SIGMA,
    lamb: float = _LAMBDA,
    tau: float = 0.0,
    block_size: float = 0.05,
    epsilon_cluster: float = _EPS_CLUSTER,
    epsilon_harmony: float = _EPS_HARMONY,
    random_state: int = 0,
    harmony2: bool = False,
    alpha: float = _ALPHA,
):
    """Batch-correct a PCA embedding with Melody. ``Z`` is ``(N, d)`` (cells x PCs, the
    orientation scanpy stores in ``obsm['X_pca']``); returns a corrected ``(N, d)`` array.

    ``batch`` is a length-``N`` array of batch labels. With fewer than two batches there is
    nothing to integrate and ``Z`` is returned unchanged. ``theta`` is the diversity
    penalty (higher = stronger mixing); ``nclust`` defaults to ``min(100, N // 30)`` per the
    paper's heuristic (§2.6.5). ``tau`` > 0 enables the small-batch theta-discounting of
    §2.6.4 (default off).

    ``harmony2`` (default ``False`` — preserves the validated 2019-method behaviour exactly)
    turns on the two clean-room **Harmony2** (Patikas et al., bioRxiv 2026) quality
    improvements, both targeting over-integration in large/heterogeneous data:
      * **stabilized diversity penalty** — the soft-assignment diversity factor's denominator
        gains an ``E_kb`` term, ``(E+1)/(O+E+1)`` instead of ``(E+1)/(O+1)``, so as a batch
        empties out of a cluster the penalty decays to ``log(1)=0`` rather than diverging;
      * **dynamic lambda** — the ridge penalty becomes per-(cluster,batch)
        ``lambda_hat_kb = alpha * E_kb`` (``alpha`` default 0.2) instead of the fixed
        ``lamb``, shrinking outlier-batch corrections toward 0.
    Both are folded in from the published preprint (not the GPL source); see
    ``docs/records/harmony2-scope/scope.md``.
    """
    Z = np.asarray(Z, dtype=np.float64)
    if Z.ndim != 2:
        raise ValueError(f"Z must be 2-D (N, d); got shape {Z.shape}")
    if not np.isfinite(Z).all():
        raise ValueError("Z contains non-finite values (NaN/inf)")

    N, d = Z.shape
    batch = np.asarray(batch)
    if batch.shape[0] != N:
        raise ValueError(f"batch length {batch.shape[0]} != number of cells {N}")

    _, codes = np.unique(batch, return_inverse=True)
    B = int(codes.max()) + 1 if N else 0
    if B < 2:
        return Z.copy()  # single batch -> no-op (the skill labels the figure accordingly)

    # Work internally in the paper's d x N orientation.
    Z_orig = np.ascontiguousarray(Z.T)              # d x N, the fixed input embedding

    phi = np.zeros((B, N))                           # B x N one-hot batch design
    phi[codes, np.arange(N)] = 1.0
    N_b = phi.sum(axis=1)                            # cells per batch
    Pr_b = N_b / N                                   # batch frequencies

    K = nclust if nclust is not None else min(100, N // 30)
    K = max(1, min(int(K), N))

    theta_b = np.full(B, float(theta))
    if tau > 0:                                      # §2.6.4 small-batch discounting
        theta_b = theta_b * (1.0 - np.exp(-N_b / (K * tau))) ** 2

    rng = np.random.default_rng(random_state)
    blocks = _make_blocks(N, block_size, rng)        # fixed deterministic partition

    # ---- one-time initialisation: KMeans on the L2-normalised input (spherical) ----
    Z_cos = _normalize_cols(Z_orig)                  # d x N, unit columns
    Y = _kmeans_init(Z_cos, K, random_state)         # d x K centroids, unit columns
    R = _soft_assign(Z_cos, Y, sigma)                # K x N, columns sum to 1
    obs = R @ phi.T                                   # K x B observed co-occurrence
    exp = np.outer(R.sum(axis=1), Pr_b)              # K x B expected co-occurrence

    Z_bar = Z_orig.copy()                            # d x N current corrected embedding
    obj_old = np.inf

    for _ in range(max_iter_harmony):
        Z_cos = _normalize_cols(Z_bar)
        R, obs, exp, Y = _cluster(
            Z_cos, phi, Pr_b, theta_b, sigma, R, obs, exp,
            blocks, max_iter_cluster, epsilon_cluster, harmony2,
        )
        Z_bar = _correct(Z_orig, R, phi, lamb, harmony2, alpha, exp)  # regress the ORIGINAL Z (§1.1)

        obj = _objective(Z_cos, Y, R, obs, exp, sigma, theta_b)
        if abs(obj_old - obj) / (abs(obj_old) + _TINY) < epsilon_harmony:
            break
        obj_old = obj

    return np.ascontiguousarray(Z_bar.T)             # back to (N, d)


# --------------------------------------------------------------------------- helpers


def _normalize_cols(M):
    """L2-normalise each column; zero columns are left as zeros (norm forced to 1)."""
    norms = np.linalg.norm(M, axis=0, keepdims=True)
    norms[norms == 0] = 1.0
    return M / norms


def _make_blocks(N, block_size, rng):
    """A fixed, seeded partition of cell indices into update blocks (~``block_size`` each)."""
    perm = rng.permutation(N)
    step = max(1, int(round(block_size * N)))
    return [perm[i : i + step] for i in range(0, N, step)]


def _kmeans_init(Z_cos, K, random_state):
    """Spherical KMeans centroids (paper: regular k-means, 10 restarts), L2-normalised."""
    from sklearn.cluster import KMeans

    km = KMeans(n_clusters=K, n_init=10, random_state=random_state)
    km.fit(Z_cos.T)                                  # cluster the (N, d) unit cells
    return _normalize_cols(km.cluster_centers_.T)    # d x K, unit columns


def _soft_assign(Z_cos, Y, sigma):
    """Distance-only soft assignment R[k,i] ∝ exp(-2(1 - Yk·Zi)/sigma), columns sum to 1.

    Used to seed R before the diversity penalty exists. Column-stabilised before exp so a
    column can never underflow to all-zeros.
    """
    dist = 2.0 * (1.0 - Y.T @ Z_cos)                 # K x N cosine distances in [0, 4]
    R = np.exp(-(dist - dist.min(axis=0, keepdims=True)) / sigma)
    return R / R.sum(axis=0, keepdims=True)


def _cluster(Z_cos, phi, Pr_b, theta_b, sigma, R, obs, exp, blocks, max_iter, epsilon, harmony2=False):
    """Algorithm 2 — maximum-diversity soft clustering on the (already normalised) embedding.

    Alternates centroid re-estimation (``Y = Z_cos R^T``, normalised) with online block
    updates of ``R`` (eq 8), keeping the observed/expected co-occurrence (``obs``/``exp``)
    consistent by leaving each block out before its update and adding it back after. Iterates
    until the clustering objective converges. ``harmony2`` switches the diversity factor's
    denominator from ``(1+O)`` (2019) to the scale-invariant ``(1+O+E)`` (Harmony2).
    """
    Y = _normalize_cols(Z_cos @ R.T)
    obj_old = _objective(Z_cos, Y, R, obs, exp, sigma, theta_b)

    for _ in range(max_iter):
        Y = _normalize_cols(Z_cos @ R.T)
        dist = 2.0 * (1.0 - Y.T @ Z_cos)             # K x N

        for blk in blocks:
            Rb = R[:, blk]
            phib = phi[:, blk]
            # Remove the block (compute the penalty context on the held-out cells).
            obs -= Rb @ phib.T
            exp -= np.outer(Rb.sum(axis=1), Pr_b)
            # Per-(cluster,batch) diversity factor raised to theta_b. Harmony1 uses the +1
            # smoothing (§2.6.3) denominator (1+O); Harmony2's stabilized penalty adds E to it
            # so that as O_kb -> 0 the factor -> (E+1)/(E+1) = 1 (penalty -> log(1)=0) instead
            # of diverging and forcing over-integration.
            denom = (1.0 + obs + exp) if harmony2 else (1.0 + obs)
            penalty = ((1.0 + exp) / denom) ** theta_b  # K x B
            # Update R on the block: distance term * diversity term, renormalised per cell.
            dblk = dist[:, blk]
            num = np.exp(-(dblk - dblk.min(axis=0, keepdims=True)) / sigma)
            num *= penalty @ phib                    # select each cell's batch column of penalty
            R[:, blk] = num / num.sum(axis=0, keepdims=True)
            # Add the updated block back into the co-occurrence matrices.
            Rb = R[:, blk]
            obs += Rb @ phib.T
            exp += np.outer(Rb.sum(axis=1), Pr_b)

        obj = _objective(Z_cos, Y, R, obs, exp, sigma, theta_b)
        if abs(obj_old - obj) / (abs(obj_old) + _TINY) < epsilon:
            break
        obj_old = obj

    return R, obs, exp, Y


def _correct(Z_orig, R, phi, lamb, harmony2=False, alpha=_ALPHA, exp=None):
    """Algorithm 3 — mixture-of-experts ridge correction of the ORIGINAL embedding.

    For each cluster k, ridge-fit ``Z`` on the augmented design ``phi* = [1; phi]`` weighted
    by ``R[k]`` (eq 14; the ridge penalises batch rows, intercept unpenalised), zero the
    intercept row, and subtract the batch-explained part. Returns the corrected ``d x N``.

    Harmony1 uses a fixed scalar ridge ``lamb`` on every batch. In ``harmony2`` mode it is
    replaced by Harmony2's **dynamic** per-(cluster,batch) penalty
    ``lambda_hat_kb = alpha * E_kb`` (``exp`` is the K x B expected co-occurrence; default
    ``alpha = 0.2``), which shrinks the correction of batches with only outlier soft
    assignments toward 0 to prevent over-integration. A tiny ``_RIDGE_FLOOR`` keeps the
    (B+1)x(B+1) solve non-singular when a (cluster,batch) cell is empty (``E_kb -> 0``).
    """
    d, N = Z_orig.shape
    K = R.shape[0]
    B = phi.shape[0]
    phi_star = np.vstack([np.ones((1, N)), phi])     # (B+1) x N
    static_ridge = np.concatenate([[0.0], np.full(B, lamb)])  # 0 on intercept (Harmony1)

    Z_bar = Z_orig.copy()
    for k in range(K):
        phi_Rk = phi_star * R[k]                      # (B+1) x N  == phi* @ diag(Rk)
        if harmony2:
            # Dynamic ridge lambda_hat_kb = alpha * E_kb, intercept unpenalised, floored.
            ridge_diag = np.concatenate([[0.0], np.maximum(alpha * exp[k], _RIDGE_FLOOR)])
        else:
            ridge_diag = static_ridge
        lhs = phi_Rk @ phi_star.T + np.diag(ridge_diag)  # (B+1) x (B+1)
        rhs = phi_Rk @ Z_orig.T                       # (B+1) x d
        W = np.linalg.solve(lhs, rhs)                 # (B+1) x d
        W[0] = 0.0                                     # keep intercept, remove batch terms
        Z_bar -= W.T @ phi_Rk                         # d x N
    return Z_bar


def _objective(Z_cos, Y, R, obs, exp, sigma, theta_b):
    """The clustering objective (eq 4): distance + sigma*entropy + sigma*diversity. Used
    only for convergence detection (relative change), so additive constants are irrelevant."""
    dist = 2.0 * (1.0 - Y.T @ Z_cos)                 # K x N
    distance = float((R * dist).sum())
    entropy = sigma * float((R * np.log(R + _TINY)).sum())
    ratio = obs / (exp + _TINY)
    diversity = sigma * float((theta_b * (obs * np.log(ratio + _TINY)).sum(axis=0)).sum())
    return distance + entropy + diversity
