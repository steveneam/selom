# RPGRIP1-style bulk DE signature oracle (edgeR, paper-faithful) — VALIDATION ONLY (ADR 0002).
# Recapitulates the authors' actual pipeline to measure Selom's pyDESeq2 delta and to test
# whether the printed signature count is reproducible AT ALL (-> blame: paper-irreproducible).
# STAR Methods (Loi 2025): featureCounts -> TMM -> CPM>=2-in-smallest-group filter ->
# 3-group NB-GLM -> glmLRT -> BH. NEVER shipped; R 4.6 is the gated blame instrument only.
#
# Usage: Rscript edger_signature.R <counts_tsv> <universe_txt> <out_dir> <ref> <treat> [treat2]
# Writes <out_dir>/result.json: {tool, version, contrast, metrics:{universe, tested,
#   signature.adj, signature.raw[, down_both.adj]}}  (signature = universe ∩ significant).
suppressMessages(library(edgeR))
a <- commandArgs(trailingOnly = TRUE)
counts_path <- a[1]; universe_path <- a[2]; out_dir <- a[3]
ref <- a[4]; treat <- a[5]; treat2 <- if (length(a) >= 6) a[6] else NA

counts <- read.delim(counts_path, row.names = 1, check.names = FALSE)
grp_raw <- sub("_.*$", "", colnames(counts))
levs <- unique(c(ref, treat, if (!is.na(treat2)) treat2 else NULL, grp_raw))
grp <- factor(grp_raw, levels = levs)

y <- DGEList(counts = counts, group = grp)
smallest <- min(table(grp))                       # CPM>=2 in >= smallest-group n samples
keep <- rowSums(cpm(y) >= 2) >= smallest
y <- y[keep, , keep.lib.sizes = FALSE]
y <- calcNormFactors(y, method = "TMM")
design <- model.matrix(~0 + grp); colnames(design) <- levels(grp)
y <- estimateDisp(y, design)
fit <- glmFit(y, design)

de <- function(tr, rf) {
  ctr <- makeContrasts(contrasts = paste0(tr, "-", rf), levels = design)
  tt <- topTags(glmLRT(fit, contrast = ctr), n = Inf)$table
  tt$gene <- rownames(tt); tt
}
uni <- readLines(universe_path); uni <- uni[nzchar(uni)]
prim <- de(treat, ref)
sig_adj <- intersect(uni, prim$gene[prim$FDR < 0.05])
sig_raw <- intersect(uni, prim$gene[prim$PValue < 0.05])

metrics <- list(universe = length(uni), tested = nrow(prim),
                "signature.adj" = length(sig_adj), "signature.raw" = length(sig_raw))
if (!is.na(treat2)) {
  sec <- de(treat2, ref)
  rownames(prim) <- prim$gene; rownames(sec) <- sec$gene
  down_both <- sig_adj[prim[sig_adj, "logFC"] < 0 & sec[sig_adj, "logFC"] < 0]
  metrics[["down_both.adj"]] <- length(down_both)
}

pairs <- paste0('"', names(metrics), '": ', unlist(metrics), collapse = ", ")
json <- paste0('{"tool": "edgeR", "version": "', as.character(packageVersion("edgeR")),
               '", "contrast": "', treat, "-", ref, '", "metrics": {', pairs, '}}')
writeLines(json, file.path(out_dir, "result.json"))
cat("DONE", json, "\n")
