# Inaccessible and deliberately deferred sources

This is the first-party crawl result, not a claim that every external source is accessible.

| URL | Observed state | Next step |
| --- | --- | --- |
| [Valuation-Cap-demo-for-blog.xlsx.zip](https://martin.kleppmann.com/2010/05/Valuation-Cap-demo-for-blog.xlsx.zip) | download_deferred: archive/XML excluded from this collector | Preserve record; targeted review/retry only if relevant. |
| [invoice.xml](https://martin.kleppmann.com/2008/11/invoice.xml) | download_deferred: archive/XML excluded from this collector | Preserve record; targeted review/retry only if relevant. |
| [Die-Tuerme-des-Februar-Einzelstimmen.zip](https://martin.kleppmann.com/die-tuerme-des-februar/downloads/Die-Tuerme-des-Februar-Einzelstimmen.zip) | download_deferred: archive/XML excluded from this collector | Preserve record; targeted review/retry only if relevant. |
| [Die-Tuerme-des-Februar-Sibelius.zip](https://martin.kleppmann.com/die-tuerme-des-februar/downloads/Die-Tuerme-des-Februar-Sibelius.zip) | download_deferred: archive/XML excluded from this collector | Preserve record; targeted review/retry only if relevant. |
| [tdf.html](https://martin.kleppmann.com/die-tuerme-des-februar/tdf.html) | fetch_error: HTTP Error 404: Not Found | Preserve record; targeted review/retry only if relevant. |

The web browsing tool initially refused the robots URL; direct public retrieval succeeded with HTTP 200. This was a tool-access limitation, not a robots-file absence.

## Continuation observations, 29 August 2026

The 2,016 external links now have reproducible triage dispositions in
`one-hop-triage.jsonl`: 117 bounded candidates, 454 other deferred artifacts and
1,445 deferred bibliography/context records. Triage is not access or reading.

| Source | Observed state | Disposition |
| --- | --- | --- |
| DDIA 2e official O'Reilly product/contents page | Indexed official contents were inspectable; direct shell capture returned HTTP 403. | Use the public section-title delta only. Do not claim chapter text or bypass access controls. |
| DDIA 2e full book text | No owner-provided lawful book file was identified in the project workspace. No private home-directory or pirated-copy scan was performed. | Unavailable and not read. The official contents, author page and licensed companion references bound this packet. |
| Cambridge supervisor solution notes | The public course page marks solution notes as Raven-gated/on demand. | Not accessed. Public 91-page lecture notes were reviewed instead. |
| Video corpus | 127 video links and one transcript-like link are triaged. No official transcript packet was selected for this capsule. | No video or unseen visual demonstration is claimed reviewed. |
| Missing V3 Kleppmann prompt | Not present in the owner package, repository or recorded filesystem search. | Explicitly unavailable and not read. Superseded for this run by the owner-accepted composite. |
| Missing standalone simplicity directive | Not present in the owner package, repository or recorded filesystem search. | Explicitly unavailable and not read. Superseded for this run by the owner-accepted composite and V4 simplicity guard. |

The exact Hermitage and DDIA 2e companion-reference repositories were publicly
accessible. Their commits and licences are recorded in the source registry. No
third-party paper, book, artifact or code was vendored into tracked repository
paths.
