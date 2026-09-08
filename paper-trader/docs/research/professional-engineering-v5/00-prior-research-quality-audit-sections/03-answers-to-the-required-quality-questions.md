Reference: [section index](../00-PRIOR-RESEARCH-QUALITY-AUDIT.md). Read with its scope; this is not a new assignment.

## Answers to the required quality questions

1. **Corpus roots claimed:** homepage, archive, talks, course post, recursively discovered first-party pages, and selected direct artifacts.
2. **Inventories used:** archive, talks, homepage publications, course resources, and later selected GitHub artifacts. No sitemap or complete GitHub-profile inventory.
3. **Opened versus listed:** clearly separated. Seven first-party records were fully read; most were only fetched or inventoried.
4. **PDFs inspected:** 29 PDFs were extracted; four exact PDFs were inspected page by page.
5. **Figures inspected:** page receipts cover the four reviewed PDFs and source notes name high-value figures. Most other PDFs and assets were not visually reviewed.
6. **Videos:** none reviewed. No claim rests on a title alone.
7. **Dates, URLs, authors, types:** canonical URLs and content types are generally present. Author, publication/update date, transcript, and licence metadata are incomplete at the counts above.
8. **Exact source locations:** strong for KCA PDF claims, weaker for umbrella HTML claims, missing for the three AUTH registry records, and absent for unreviewed items.
9. **Citation support:** mixed. General principles usually hold; several Strategy OS-specific sentences exceed the cited source.
10. **Source, inference, recommendation separation:** inadequate in the machine registry. Narrative notes often separate them better than the JSONL.
11. **Repository paths and lines:** paths exist and ranges are in bounds, but several implementation-state claims are stale.
12. **Genuinely new findings:** KCA-001 and NMT-001 through NMT-005 supplied new or sharpened failure hypotheses. Many KCA items confirm existing invariants or reject unnecessary machinery.
13. **Prestige-driven technology:** no. The programme consistently rejects Kafka, Redis authority, workflow platforms, CRDTs, and sharding without direct need.
14. **Code without failing evidence:** the prior research capsules were production-code-read-only. Later corrections used separate capsules. No research-driven product mutation was found in the audited artifacts.
15. **Unavailable sources:** honestly recorded, including missing V3/simplicity files, DDIA 2e book text, the O'Reilly shell 403, videos, and deferred archives.
16. **Source conflicts:** Redlock disagreement is represented. Most other source families were too lightly reviewed to expose meaningful disagreements.
17. **Current versus future releases:** generally separated. Older V1.1 labels are now superseded and must not re-enter current classifications.
18. **Anti-overengineering:** followed in recommendations and actual writes.
19. **Reproducibility:** good for retrieval, hashes, generated manifests, selected probes, and validators; incomplete for human reading and any ignored cache absent from a future checkout.
20. **Retain, correct, discard, re-review:** retain evidence custody and narrow findings; correct registry schema and stale statuses; do not discard unread inventory; re-review high-value unread sources; reject completion claims.

## Required correction policy for V5

V5 will not rewrite old claim history. It will append new V5 source and claim records with distinct fields for:

- exact source-supported claim;
- source assumptions and system model;
- Codex inference;
- Strategy OS repository mapping;
- failure hypothesis;
- current implementation state;
- recommended response and release;
- verification still required.

Old claims remain historical evidence. V5 claims will mark stale or superseded implementation state explicitly and will not relabel an accepted correction as pending.

## Evidence paths

- `.agent/runs/kleppmann-reaudit-v5/root-orientation/orientation-receipt.md`
- `.agent/runs/kleppmann-reaudit-v5/prior-research-audit/artifact-metadata.log`
- `.agent/runs/kleppmann-reaudit-v5/prior-research-audit/manifest-quality-metrics.log`
- `.agent/runs/kleppmann-reaudit-v5/prior-research-audit/claim-structure-audit.log`
- `.agent/runs/kleppmann-reaudit-v5/prior-research-audit/source-registry-structure-audit.log`
- `.agent/runs/kleppmann-reaudit-v5/prior-research-audit/citation-sample.log`
- `.agent/runs/kleppmann-reaudit-v5/prior-research-audit/fresh-source-hashes.log`
- `.agent/runs/kleppmann-reaudit-v5/prior-research-audit/sampled-pdf-text.log`
- `.agent/runs/kleppmann-reaudit-v5/prior-research-audit/visuals/`
