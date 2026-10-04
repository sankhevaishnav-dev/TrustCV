"""Transparent MVP risk rules; statuses describe findings, not safety proofs."""

from __future__ import annotations


def assess(dataset=None, model_matches: bool | None = None, chain_valid: bool | None = None) -> list[dict[str, str]]:
    findings = []
    if dataset is None:
        findings.append({"area": "Dataset", "status": "WARNING", "reason": "No dataset scan has been run in this session."})
    elif dataset.empty:
        findings.append({"area": "Dataset", "status": "WARNING", "reason": "No supported image files were found in the scan."})
    else:
        valid = int(dataset["valid"].sum()) if not dataset.empty else 0
        unreadable = int((~dataset["valid"]).sum()) if not dataset.empty else 0
        duplicates = int(dataset["exact_duplicate"].sum()) if not dataset.empty else 0
        content_duplicates = int(dataset["content_duplicate"].sum()) if not dataset.empty else 0
        status = "HIGH RISK" if unreadable else ("WARNING" if duplicates or content_duplicates else "PASS")
        findings.append({"area": "Dataset", "status": status,
                         "reason": f"{valid} valid, {unreadable} unreadable, {duplicates} exact-duplicate entry/entries, {content_duplicates} identical-pixel entry/entries. Checks do not identify all poisoning or label issues."})
    if model_matches is None:
        findings.append({"area": "Model", "status": "WARNING", "reason": "No trusted reference hash has been saved or compared."})
    else:
        findings.append({"area": "Model", "status": "PASS" if model_matches else "HIGH RISK",
                         "reason": "Uploaded model hash matches the saved local reference." if model_matches else "Uploaded model hash differs from the saved local reference."})
    if chain_valid is None:
        findings.append({"area": "Inference audit", "status": "WARNING", "reason": "No audit-chain verification has been run."})
    else:
        findings.append({"area": "Inference audit", "status": "PASS" if chain_valid else "HIGH RISK",
                         "reason": "Stored audit hash chain verifies." if chain_valid else "Stored audit chain has a mismatch."})
    return findings
