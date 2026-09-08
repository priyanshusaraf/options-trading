# Exact source preservation

`originals.tar.gz` preserves exact source bytes from before whitespace normalization. `manifest.json` maps each original repository path to its original SHA-256, byte count, and readable-copy SHA-256. The archive is deterministic: sorted paths, zero timestamps and ownership, fixed permissions, and gzip timestamp zero.

Historical receipts and supplied-source hashes refer to the archive member at the recorded repository path. They do not assert that the normalized readable copy has the original hash. Original owner directions remain authoritative as preserved bytes; the readable documents are equivalent copies with Markdown hard breaks represented by backslashes, CRLF converted to LF, and excess EOF blank lines removed. These changes grant no new scope or dispatch authority. The two archived recovery capsules remain frozen and non-executable under CURRENT.md.

`../strategy-os-v1-v2-v3/validation/source_preservation.py` verifies the archive hash, each original source hash, and exact permitted normalization against the readable copy. The architecture validator uses this resolver for the supplied product memo while retaining its original expected SHA-256. To inspect an original, read its manifest path directly from the tar archive; do not substitute the readable-copy hash in old seals.
