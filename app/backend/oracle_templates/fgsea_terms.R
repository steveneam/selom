# fgsea term-count oracle on Selom's OWN rankings — VALIDATION ONLY (ADR 0002).
# Runs the authors' actual GSEA tool (fgsea) on the SAME ranked lists + SAME C5 gene sets
# Selom scored with gseapy.prerank, to split the GSEA-engine delta (fgsea >> gseapy term
# counts, RISKS #10 -> engine-delta) from the upstream rod-subtype delta (a shared core that
# even fgsea can't recover -> upstream-delta). NEVER shipped; the gated blame instrument only.
#
# Usage: Rscript fgsea_terms.R <gmt> <rnk_dir> <out_dir> <rod1> [rod2 rod3 ...]
#   reads <rnk_dir>/ranked_<rod>.rnk  (gene\tscore, written by the gsea panel run)
# Writes <out_dir>/result.json: {tool, version, metrics:{<rod>.count, [venn.* for 3 rods]}}.
suppressMessages(library(fgsea))
a <- commandArgs(trailingOnly = TRUE)
gmt_path <- a[1]; rnk_dir <- a[2]; out_dir <- a[3]; rods <- a[-(1:3)]
gmt <- gmtPathways(gmt_path)
sig <- list(); counts <- c()
for (rt in rods) {
  tab <- read.table(file.path(rnk_dir, paste0("ranked_", rt, ".rnk")),
                    header = FALSE, sep = "\t", stringsAsFactors = FALSE)
  ranks <- setNames(as.numeric(tab[[2]]), tab[[1]]); ranks <- ranks[!is.na(ranks)]
  set.seed(0)
  fg <- fgseaMultilevel(pathways = gmt, stats = ranks, minSize = 10, maxSize = 2000)
  up <- fg[fg$padj < 0.05 & fg$NES > 0, ]
  sig[[rt]] <- up$pathway; counts[rt] <- nrow(up)
}
metrics <- list()
for (rt in rods) metrics[[paste0(rt, ".count")]] <- counts[[rt]]
if (length(rods) == 3) {
  s1 <- sig[[rods[1]]]; s2 <- sig[[rods[2]]]; s3 <- sig[[rods[3]]]
  metrics[["venn.r1_only"]] <- length(setdiff(setdiff(s1, s2), s3))
  metrics[["venn.r2_only"]] <- length(setdiff(setdiff(s2, s1), s3))
  metrics[["venn.r3_only"]] <- length(setdiff(setdiff(s3, s1), s2))
  metrics[["venn.r1n2"]] <- length(setdiff(intersect(s1, s2), s3))
  metrics[["venn.r1n3"]] <- length(setdiff(intersect(s1, s3), s2))
  metrics[["venn.r2n3"]] <- length(setdiff(intersect(s2, s3), s1))
  metrics[["venn.all_three"]] <- length(intersect(intersect(s1, s2), s3))
}
pairs <- paste0('"', names(metrics), '": ', unlist(metrics), collapse = ", ")
json <- paste0('{"tool": "fgsea", "version": "', as.character(packageVersion("fgsea")),
               '", "metrics": {', pairs, '}}')
writeLines(json, file.path(out_dir, "result.json"))
cat("DONE", json, "\n")
