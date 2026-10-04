"""TrustCV local-first computer-vision integrity dashboard."""

from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from trustcv.dataset import MAX_FILE_BYTES, scan_images
from trustcv.hashing import hash_matches, sha256_stream
from trustcv.inference import classify_image
from trustcv.risk import assess
from trustcv.storage import add_audit, configured_db_path, get_reference_hash, list_audits, set_reference_hash, verify_chain

st.set_page_config(page_title="TrustCV | Integrity Assurance", page_icon="🛡️", layout="wide")

DB_PATH = configured_db_path()
PAGES = ["Overview", "Dataset Scanner", "Model Verification", "Inference Audit", "Audit History", "Evidence Reports"]
NAV_LABELS = {
    "Dashboard": "Overview", "Data Check": "Dataset Scanner", "Model Check": "Model Verification",
    "Inference Check": "Inference Audit", "Evidence": "Audit History", "Reports": "Evidence Reports",
}
STATUS_COLORS = {"PASS": "#45d6ab", "WARNING": "#f5c45c", "HIGH RISK": "#ff737d"}

st.markdown(
    """
    <style>
    :root { --tc-bg:#07111c; --tc-panel:#0d1b29; --tc-panel2:#102234; --tc-line:#1d3548;
      --tc-ink:#edf5f8; --tc-muted:#9ab0bf; --tc-cyan:#56d7e8; --tc-teal:#56d6b0; }
    .block-container { padding:1.2rem 2rem 3rem; max-width:1500px; }
    [data-testid="stAppViewContainer"], [data-testid="stApp"] { background:var(--tc-bg); color:var(--tc-ink); }
    [data-testid="stHeader"] { background:rgba(7,17,28,.82); }
    [data-testid="stSidebar"] { background:#091521; border-right:1px solid var(--tc-line); }
    [data-testid="stSidebar"] > div:first-child { padding-top:1.25rem; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { padding:.32rem .25rem; color:var(--tc-muted); }
    [data-testid="stSidebar"] [data-testid="stRadio"] > label { color:#7290a3; font-size:.7rem; font-weight:750; letter-spacing:.12em; }
    .tc-sidebar-brand { display:flex; align-items:center; gap:.7rem; padding:.1rem .1rem 1rem; }
    .tc-logo { display:grid; place-items:center; width:2.55rem; height:2.55rem; border-radius:.8rem;
      background:linear-gradient(145deg,#123a50,#176b87); color:#bdf7f6; font-size:.88rem; font-weight:800; letter-spacing:.03em; box-shadow:0 0 22px #36b9d326; }
    .tc-sidebar-name { color:var(--tc-ink); font-size:1.25rem; line-height:1.1; font-weight:780; letter-spacing:-.035em; }
    .tc-sidebar-caption { color:var(--tc-muted); font-size:.78rem; margin-top:.22rem; }
    .tc-topbar { display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:1.1rem 1.35rem;
      border:1px solid #21445a; border-radius:1rem; background:radial-gradient(ellipse at 92% 15%,#163d51 0%,transparent 46%),linear-gradient(112deg,#0c1a28,#0d2434);
      box-shadow:0 14px 40px #0003,inset 0 1px #ffffff09; color:#fff; margin-bottom:1.05rem; }
    .tc-topbrand { display:flex; align-items:center; gap:.8rem; }
    .tc-toplogo { display:grid; place-items:center; width:2.8rem; height:2.8rem; border-radius:.85rem;
      color:#bff8f2; background:linear-gradient(145deg,#153c50,#102838); border:1px solid #3b91a2; font-size:1rem; font-weight:850; box-shadow:0 0 24px #34c3d01c; }
    .tc-topname { color:#f2f8fa; font-size:1.27rem; line-height:1.1; font-weight:760; letter-spacing:-.025em; }
    .tc-topcaption { color:#a4bbc8; font-size:.78rem; margin-top:.24rem; }
    .tc-pipeline { color:#d7e9ee; font-size:.8rem; font-weight:700; letter-spacing:.035em; text-align:right; }
    .tc-pipeline small { display:block; margin-top:.32rem; color:#8eabba; font-size:.69rem; font-weight:500; }
    .tc-kicker { color:var(--tc-cyan); font-size:.68rem; letter-spacing:.15em; font-weight:750; text-transform:uppercase; }
    .tc-page-title { color:var(--tc-ink); font-size:1.8rem; line-height:1.2; font-weight:730; letter-spacing:-.035em; margin:.18rem 0 .3rem; }
    .tc-status { display:inline-flex; align-items:center; padding:.32rem .65rem; border-radius:999px;
      font-size:.7rem; font-weight:780; letter-spacing:.055em; border:1px solid currentColor; white-space:nowrap; }
    .tc-local { color:#aeeef0; background:#0e2b39; border:1px solid #235366; border-radius:999px;
      display:inline-block; padding:.35rem .62rem; font-size:.68rem; font-weight:700; letter-spacing:.045em; }
    .tc-muted { color:var(--tc-muted); font-size:.88rem; line-height:1.5; }
    .tc-step { position:relative; border:1px solid var(--tc-line); background:linear-gradient(145deg,#102234,#0b1825); border-radius:.85rem; padding:.9rem 1rem; min-height:5rem; transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease; }
    .tc-step:hover { transform:translateY(-2px); border-color:#34778a; box-shadow:0 8px 24px #0003,0 0 16px #36b9d314; }
    .tc-step:not(.tc-step-last)::after { content:"→"; position:absolute; right:-.82rem; top:1.6rem; z-index:2; color:#56d7e8; font-size:1.05rem; animation:tc-flow 2.2s ease-in-out infinite; }
    .tc-step b { display:block; color:#edf5f8; font-size:.82rem; letter-spacing:.04em; margin-bottom:.35rem; }
    .tc-step span { color:var(--tc-muted); font-size:.76rem; line-height:1.4; }
    .tc-stage-state { float:right; color:#a9bac6; font-size:.62rem; font-weight:650; letter-spacing:.04em; }
    .tc-hero { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:1.4rem 1.5rem; border-radius:1rem;
      border:1px solid #214257; background:radial-gradient(ellipse at 88% 50%,#12394a 0%,transparent 40%),linear-gradient(110deg,#0e1d2b,#0d2231); box-shadow:inset 0 1px #ffffff09; }
    .tc-hero h2 { color:#f1f7f9; font-size:1.55rem; margin:.2rem 0 .4rem; letter-spacing:-.035em; }
    .tc-hero p { color:#9eb3c1; font-size:.9rem; margin:0; }
    .tc-hero-note { margin-top:.85rem; color:#94aebe; font-size:.78rem; }
    .tc-hero-note b { color:#f5d889; font-weight:700; }
    .tc-orb { width:116px; height:116px; flex:0 0 116px; display:grid; place-items:center; border-radius:50%;
      border:2px solid #f5c45c; box-shadow:0 0 0 8px #f5c45c12,0 0 32px #f5c45c1c,inset 0 0 22px #f5c45c12;
      color:#f5d889; font-weight:800; font-size:.77rem; letter-spacing:.06em; text-align:center; }
    .tc-empty { border:1px dashed #294354; background:#0d1b29; border-radius:.9rem; padding:1.15rem 1.25rem; }
    .tc-empty-title { color:var(--tc-ink); font-weight:700; font-size:.95rem; margin-bottom:.28rem; }
    .tc-empty-detail,.tc-empty-action { color:var(--tc-muted); font-size:.84rem; line-height:1.5; }
    .tc-empty-action { margin-top:.35rem; }
    div[data-testid="stMetric"] { background:linear-gradient(145deg,#102132,#0c1926); border:1px solid var(--tc-line); padding:.85rem 1rem; border-radius:.8rem; box-shadow:inset 0 1px #ffffff08; }
    div[data-testid="stMetricLabel"] { color:var(--tc-muted); font-size:.79rem; }
    div[data-testid="stMetricValue"] { color:#edf5f8; font-size:1.48rem; }
    [data-testid="stProgressBar"] > div > div { background:linear-gradient(90deg,#56d6b0,#56d7e8); }
    [data-testid="stDataFrame"] { border:1px solid var(--tc-line); border-radius:.75rem; overflow:hidden; }
    .tc-section-label { color:#7290a3; font-size:.68rem; font-weight:750; letter-spacing:.14em; margin:1.25rem 0 .65rem; }
    [data-testid="stRadio"] > div { gap:.35rem; }
    [data-testid="stRadio"] label { color:#c4d4dd; }
    div[data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] { gap:.45rem; flex-wrap:wrap; }
    div[data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] label[data-baseweb="radio"] { border:1px solid #1d3548; border-radius:999px; padding:.35rem .72rem; background:#0b1825; transition:all .16s ease; }
    div[data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] label[data-baseweb="radio"]:has(input:checked) { border-color:#3b91a2; background:#103043; color:#c7f6f4; box-shadow:0 0 16px #56d7e815; }
    [data-testid="stButton"] button[kind="primary"] { color:#04141c; background:#56d7e8; border-color:#56d7e8; font-weight:750; transition:all .18s ease; }
    [data-testid="stButton"] button[kind="primary"]:hover { background:#8beaf2; border-color:#8beaf2; box-shadow:0 0 20px #56d7e830; }
    [data-testid="stExpander"] { border-color:var(--tc-line); background:#0c1926; border-radius:.75rem; }
    [data-testid="stAlert"] { border:1px solid var(--tc-line); }
    .tc-demo-step { animation:tc-glow 2.8s ease-in-out infinite alternate; }
    @keyframes tc-flow { 0%,100% { opacity:.5; transform:translateX(-2px); } 50% { opacity:1; transform:translateX(2px); } }
    @keyframes tc-glow { from { border-color:#1d3548; } to { border-color:#39849a; box-shadow:0 0 18px #56d7e81c; } }
    @media (prefers-reduced-motion: reduce) { *,*::before,*::after { animation-duration:.01ms!important; transition-duration:.01ms!important; scroll-behavior:auto!important; } }
    @media (max-width:900px) { .block-container { padding-left:1.2rem; padding-right:1.2rem; }
      .tc-topbar { align-items:flex-start; flex-direction:column; } .tc-pipeline { text-align:left; }
      .tc-hero { align-items:flex-start; } .tc-orb { width:92px;height:92px;flex-basis:92px; }
      .tc-step:not(.tc-step-last)::after { display:none; } }
    @media (max-width:620px) { .tc-hero { flex-direction:column; } .tc-page-title { font-size:1.55rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def status_badge(status: str) -> None:
    color = STATUS_COLORS.get(status, "#637587")
    st.markdown(
        f'<span class="tc-status" style="color:{color};background:{color}12">{status}</span>',
        unsafe_allow_html=True,
    )


def page_heading(title: str, description: str) -> None:
    safe_title = html.escape(title)
    safe_description = html.escape(description)
    st.markdown(f'<div class="tc-kicker">WORKSPACE / {safe_title.upper()}</div><div class="tc-page-title">{safe_title}</div><div class="tc-muted">{safe_description}</div>', unsafe_allow_html=True)
    st.write("")


def overall_status(findings: list[dict[str, str]]) -> str:
    statuses = {finding["status"] for finding in findings}
    if "HIGH RISK" in statuses:
        return "HIGH RISK"
    if "WARNING" in statuses:
        return "WARNING"
    return "PASS"


def safe_count(frame: pd.DataFrame | None, column: str) -> int:
    if frame is None or frame.empty or column not in frame:
        return 0
    return int(frame[column].sum())


def show_empty_state(title: str, detail: str, action: str | None = None) -> None:
    action_html = f'<div class="tc-empty-action">{html.escape(action)}</div>' if action else ""
    st.markdown(
        f'<div class="tc-empty"><div class="tc-empty-title">{html.escape(title)}</div>'
        f'<div class="tc-empty-detail">{html.escape(detail)}</div>{action_html}</div>',
        unsafe_allow_html=True,
    )


def select_nav(label: str) -> None:
    st.session_state["top_navigation"] = label


for key, initial in (("dataset_scan", None), ("dataset_scan_at", None), ("model_matches", None),
                     ("last_inference", None), ("last_inference_image_hash", None), ("presentation_mode", False)):
    if key not in st.session_state:
        st.session_state[key] = initial

with st.sidebar:
    st.markdown(
        '<div class="tc-sidebar-brand"><div class="tc-logo">TC</div><div><div class="tc-sidebar-name">TrustCV</div><div class="tc-sidebar-caption">Integrity assurance</div></div></div>',
        unsafe_allow_html=True,
    )
    st.divider()
    with st.expander("Presentation settings", expanded=True):
        st.session_state.presentation_mode = st.toggle("Presentation mode", key="presentation_toggle")
        st.caption("Highlights the pipeline using current results. It does not create findings or run checks automatically.")
        st.caption(f"Audit store: `{DB_PATH}`")
    st.markdown("<span class='tc-local'>RUNTIME-LOCAL · SQLITE</span>", unsafe_allow_html=True)
    st.caption("Model uploads are hashed as bytes. They are never executed.")

st.markdown(
    '<div class="tc-topbar"><div class="tc-topbrand"><div class="tc-toplogo">TC</div>'
    '<div><div class="tc-topname">TrustCV</div><div class="tc-topcaption">Computer vision integrity assurance</div></div></div>'
    '<div class="tc-pipeline">DATA <span style="color:#9ac8d4">→</span> MODEL <span style="color:#9ac8d4">→</span> INFERENCE <span style="color:#9ac8d4">→</span> RISK'
    '<small>Runtime-local operator session · SQLite audit history</small></div></div>',
    unsafe_allow_html=True,
)

nav_choice = st.radio("TrustCV sections", list(NAV_LABELS), horizontal=True, label_visibility="collapsed", key="top_navigation")
page = NAV_LABELS[nav_choice]
st.markdown('<div style="height:.4rem"></div>', unsafe_allow_html=True)


if page == "Overview":
    page_heading("Dashboard", "Lightweight security middleware for computer-vision pipelines. See what was checked and follow the evidence.")
    audit_records = list_audits(DB_PATH)
    chain_valid, chain_message = verify_chain(DB_PATH)
    findings = assess(st.session_state.dataset_scan, st.session_state.model_matches,
                      chain_valid if audit_records else None)
    status = overall_status(findings)
    dataset = st.session_state.dataset_scan
    dataset_count = len(dataset) if dataset is not None else 0
    model_state = "MATCHED" if st.session_state.model_matches is True else ("MISMATCH" if st.session_state.model_matches is False else "NOT CHECKED")
    data_state = "NOT SCANNED" if dataset is None else ("REVIEW" if findings[0]["status"] != "PASS" else "PASS")
    inference_state = "NOT CHECKED" if not audit_records else ("CHAIN VALID" if chain_valid else "CHAIN MISMATCH")
    open_findings = sum(item["status"] != "PASS" for item in findings)
    status_color = STATUS_COLORS[status]

    st.markdown(
        f'<div class="tc-hero"><div><div class="tc-kicker">LIVE PIPELINE POSTURE</div>'
        f'<h2>Computer Vision Integrity Center</h2>'
        f'<p>Monitor dataset, model, and inference evidence in one runtime-local assurance view.</p>'
        f'<div class="tc-hero-note">Integrity score: <b>not calculated</b> · rule-based findings only</div></div>'
        f'<div class="tc-orb" style="border-color:{status_color};color:{status_color};box-shadow:0 0 0 8px {status_color}18,0 0 32px {status_color}28">SYSTEM<br>{status}</div></div>',
        unsafe_allow_html=True,
    )
    if st.session_state.presentation_mode:
        st.info("Presentation mode is highlighting the current pipeline view. No checks run automatically and no sample findings are generated.")

    last_scan = "Not scanned"
    if st.session_state.dataset_scan_at:
        last_scan = datetime.fromisoformat(st.session_state.dataset_scan_at).strftime("%d %b · %H:%M UTC")
    m_score, m_scan, m_findings, m_records = st.columns(4)
    m_score.metric("Integrity score", "Not scored")
    m_scan.metric("Last dataset scan", last_scan)
    m_findings.metric("Open checks / findings", open_findings)
    m_records.metric("Evidence records", len(audit_records))

    st.subheader("Integrity pipeline")
    data_detail = "No dataset scan yet" if dataset is None else f"{safe_count(dataset, 'valid')} decodable · {safe_count(dataset, 'exact_duplicate')} exact dupes · {safe_count(dataset, 'content_duplicate')} pixel matches"
    model_detail = "Saved hash matched" if st.session_state.model_matches is True else ("Reference mismatch" if st.session_state.model_matches is False else "No comparison recorded")
    inference_detail = f"{len(audit_records)} record(s) · {inference_state.lower()}" if audit_records else "No inference audits yet"
    risk_detail = f"{open_findings} open assessment(s) · {status}"
    pipeline = [
        ("DATA", data_state, data_detail, "Data Check"),
        ("MODEL", model_state, model_detail, "Model Check"),
        ("INFERENCE", inference_state, inference_detail, "Inference Check"),
        ("RISK", status, risk_detail, "Reports"),
    ]
    stage_cols = st.columns(4)
    for stage_index, (col, (name, state, detail, destination)) in enumerate(zip(stage_cols, pipeline)):
        with col:
            demo_class = " tc-demo-step" if st.session_state.presentation_mode else ""
            last_class = " tc-step-last" if stage_index == len(pipeline) - 1 else ""
            st.markdown(f'<div class="tc-step{demo_class}{last_class}"><b>{name} <span class="tc-stage-state">{html.escape(state)}</span></b><span>{html.escape(detail)}</span></div>', unsafe_allow_html=True)
            st.button(f"Open {name.title()}", key=f"open_{name.lower()}", on_click=select_nav, args=(destination,), use_container_width=True)

    st.markdown("<div class='tc-section-label'>ASSESSMENT SUMMARY</div>", unsafe_allow_html=True)
    assessment_cols = st.columns(3)
    for col, finding in zip(assessment_cols, findings):
        with col, st.container(border=True):
            status_badge(finding["status"])
            st.markdown(f"**{finding['area']}**")
            st.write(finding["reason"])

    chart_col, recommendation_col = st.columns([1.1, 1])
    with chart_col, st.container(border=True):
        st.markdown("**Assessment distribution**")
        distribution = pd.DataFrame({"Checks": [sum(x["status"] == level for x in findings) for level in ("PASS", "WARNING", "HIGH RISK")]}, index=["PASS", "WARNING", "HIGH RISK"])
        st.bar_chart(distribution, color="#56D7E8", height=210)
        st.caption("Counts are derived from the three current rule-based assessment areas; they are not a risk score.")
    with recommendation_col, st.container(border=True):
        st.markdown("**Recommended next action**")
        if status == "HIGH RISK":
            st.error("Review the model mismatch, unreadable dataset entries, or chain-link failure before relying on the affected evidence.")
        elif status == "WARNING":
            st.warning("Complete the unchecked comparisons and review duplicate groups. Missing checks remain visible as warnings.")
        else:
            st.success("Configured checks passed. This is not a safety certification.")
        st.caption("TrustCV checks file integrity and audit linkage; label anomalies, OOD, trigger patterns, replay, and model metadata are not assessed by this MVP.")

    st.subheader("Evidence / provenance chain")
    st.caption("Every displayed row comes from the SQLite audit log. Output hashes and model versions are not currently recorded.")
    if not audit_records:
        show_empty_state("No evidence records", "Run an inference audit to create the first input → model → output record.")
    else:
        for record in reversed(audit_records[:3]):
            with st.expander(f"Record #{record['id']} · {record['prediction']} · {record['timestamp_utc']} UTC", expanded=False):
                chain_cols = st.columns(3)
                chain_cols[0].markdown("**INPUT SHA-256**")
                chain_cols[0].code(record["image_sha256"])
                chain_cols[1].markdown("**MODEL IDENTIFIER / HASH**")
                chain_cols[1].code(record["model_sha256"])
                chain_cols[2].markdown("**OUTPUT**")
                chain_cols[2].write(record["prediction"])
                st.caption(f"Mode: {record['mode']} · Confidence: {record['confidence'] if record['confidence'] is not None else 'not available'} · Previous hash: {record['previous_hash'][:16]}… · Record hash: {record['record_hash'][:16]}…")
    with st.expander("What this MVP does not assess"):
        st.markdown("- Dataset label anomalies, out-of-distribution samples, and trigger-pattern attacks.\n- Model version and metadata provenance.\n- Inference replay or prediction-output hash matching.\n- A numeric composite integrity score.\n\nThese are not inferred from the sample numbers shown in external pitch materials.")
    st.caption(f"Audit database: `{DB_PATH}` · {chain_message}")


elif page == "Dataset Scanner":
    page_heading("Dataset scanner", "Check whether image files decode, compare file hashes, and group identical decoded pixels.")
    with st.container(border=True):
        uploads = st.file_uploader("Add image files or ZIP archives", type=["jpg", "jpeg", "png", "bmp", "gif", "tif", "tiff", "webp", "zip"], accept_multiple_files=True)
        left, right = st.columns([1, 2])
        with left:
            scan_clicked = st.button("Scan dataset", type="primary", disabled=not uploads, use_container_width=True)
        with right:
            st.caption("Up to 100 MiB combined · up to 25 MiB per image · ZIP contents are scanned in memory")
    if scan_clicked:
        total_size = sum(upload.size for upload in uploads)
        if total_size > 100 * 1024 * 1024:
            st.error("Combined upload exceeds the 100 MiB limit. Remove some files and try again.")
        else:
            with st.spinner("Checking image decoding and duplicate hashes…"):
                st.session_state.dataset_scan = scan_images((item.name, item.getvalue()) for item in uploads)
                st.session_state.dataset_scan_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    result = st.session_state.dataset_scan
    if result is None:
        show_empty_state("No scan results yet", "Choose images or a ZIP above, then start a scan.", "Duplicate checks are exact-file and identical-pixel heuristics; they do not detect every poisoned or mislabeled sample.")
    else:
        warnings = result.attrs.get("warnings", [])
        for warning in warnings:
            st.warning(warning)
        total = len(result)
        valid = safe_count(result, "valid")
        unreadable = total - valid
        exact_duplicates = safe_count(result, "exact_duplicate")
        pixel_duplicates = safe_count(result, "content_duplicate")
        duplicate_entries = int((result["exact_duplicate"] | result["content_duplicate"]).sum()) if total else 0
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Files checked", total)
        m2.metric("Decodable", valid)
        m3.metric("Unreadable", unreadable)
        m4.metric("Duplicate entries flagged", duplicate_entries)
        if total:
            st.progress(valid / total, text=f"Decode success: {valid} of {total} file(s)")
        detail_left, detail_right = st.columns(2)
        detail_left.caption(f"Exact duplicate entries · {exact_duplicates}")
        detail_right.caption(f"Identical-pixel entries · {pixel_duplicates}")
        if total:
            with st.expander("Dataset composition and coverage", expanded=False):
                composition, coverage = st.columns([1, 1.2])
                with composition:
                    st.markdown("**Decode outcome**")
                    st.bar_chart(pd.DataFrame({"Files": [valid, unreadable]}, index=["Decodable", "Unreadable"]), color="#56D7E8", height=190)
                with coverage:
                    st.markdown("**Checks performed by this scanner**")
                    st.write("✓ Image decoding · ✓ Exact file hashes · ✓ Identical decoded pixels")
                    st.markdown("**Not assessed by this MVP**")
                    st.write("Label anomalies · out-of-distribution samples · trigger patterns · semantic/near-duplicate images")
        current = result.copy()
        if "sha256" in current:
            current["sha256"] = current["sha256"].map(lambda value: f"{value[:12]}…{value[-8:]}" if isinstance(value, str) and len(value) > 24 else value)
        current = current.drop(columns=["content_hash"], errors="ignore")
        st.dataframe(current, use_container_width=True, hide_index=True,
                     column_config={"sha256": st.column_config.TextColumn("SHA-256 (short)", help="CSV export contains the full hash."),
                                    "valid": st.column_config.CheckboxColumn("Decodable")})
        st.download_button("Download full scan CSV", result.to_csv(index=False).encode("utf-8-sig"), "trustcv_dataset_scan.csv", "text/csv")
        st.caption(result.attrs.get("limitations", ""))
        st.caption(f"Exact duplicate entries: {exact_duplicates} · Identical decoded-pixel entries: {pixel_duplicates}")


elif page == "Model Verification":
    page_heading("Model verification", "Compare the SHA-256 of an uploaded artifact with a trusted reference saved in this app runtime.")
    st.warning("A hash comparison is only as trustworthy as the reference hash. Obtain that reference through a secure, trusted channel.")
    model_file = st.file_uploader("Choose a model artifact (up to 100 MiB)", type=None, key="model_upload", help="The file is read as bytes to calculate SHA-256; it is never loaded or executed.")
    if model_file:
        if model_file.size > 100 * 1024 * 1024:
            st.error("Model exceeds the 100 MiB upload limit.")
        else:
            with st.spinner("Calculating SHA-256…"):
                model_hash = sha256_stream(model_file)
            reference = get_reference_hash(DB_PATH)
            calc_col, expected_col = st.columns(2)
            with calc_col, st.container(border=True):
                st.markdown("**CALCULATED SHA-256**")
                st.code(model_hash, language=None)
            with expected_col, st.container(border=True):
                st.markdown("**EXPECTED / SAVED REFERENCE**")
                st.code(reference if reference else "No reference saved", language=None)
            if reference:
                matches = hash_matches(model_hash, reference)
                st.session_state.model_matches = matches
                status_badge("PASS" if matches else "HIGH RISK")
                st.success("The uploaded file matches the saved reference hash.") if matches else st.error("The uploaded file does not match the saved reference hash.")
            else:
                st.session_state.model_matches = None
                status_badge("WARNING")
                st.info("No reference hash is saved yet. Save one only if you trust how that reference was obtained.")
            if st.button("Save uploaded hash as trusted reference", type="primary", disabled=not model_hash):
                set_reference_hash(model_hash, DB_PATH)
                st.session_state.model_matches = True
                st.success("Reference hash saved in runtime-local SQLite settings.")
            with st.expander("Additional model metadata", expanded=False):
                st.write("Version, architecture, provenance, and embedded metadata are not inspected by this MVP. The artifact is hashed as bytes and never deserialized or executed.")
    else:
        saved_reference = get_reference_hash(DB_PATH)
        if saved_reference:
            status_badge("WARNING")
            st.write("A saved reference exists in this app runtime. Upload a model file to compare against it.")
            with st.expander("View saved reference hash"):
                st.code(saved_reference, language=None)
        else:
            show_empty_state("No model checked", "Upload a model file to calculate its SHA-256 hash.", "Files are hashed only; model artifacts are never loaded or executed.")


elif page == "Inference Audit":
    page_heading("Inference audit", "Run an explicit demo result or try ImageNet ResNet-18, then save a hash-linked audit record.")
    mode = st.radio("Choose inference mode", ["Demo mode · offline, no classification", "Pretrained ResNet-18 · may download weights"], horizontal=True, index=0)
    st.caption("Demo mode does not classify the image and does not produce a confidence score.")
    image_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png", "bmp", "webp"], key="audit_image")
    if not image_file:
        show_empty_state("Ready for an image", "Upload a supported image to begin the audit.", "Pretrained mode uses ImageNet categories and may need internet on its first run.")
    else:
        image_bytes = image_file.getvalue()
        if len(image_bytes) > MAX_FILE_BYTES:
            st.error("Image exceeds the 25 MiB limit.")
        else:
            image_hash = hashlib.sha256(image_bytes).hexdigest()
            preview, details = st.columns([1, 2])
            with preview:
                try:
                    st.image(image_bytes, caption="Uploaded input", use_container_width=True)
                except Exception:
                    st.error("This file could not be displayed as an image.")
            with details:
                st.markdown("**Input SHA-256**")
                st.code(image_hash, language=None)
                if st.button("Run and record inference", type="primary", use_container_width=True):
                    with st.spinner("Running selected inference mode and saving the audit record…"):
                        result = classify_image(image_bytes, use_pretrained=mode.startswith("Pretrained"))
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            record = add_audit(image_hash, result["model_sha256"], result["prediction"], result["confidence"], result["mode"], DB_PATH)
                            st.session_state.last_inference = result
                            st.session_state.last_inference_image_hash = image_hash
                            st.session_state.last_record = record
                result = st.session_state.last_inference if st.session_state.last_inference_image_hash == image_hash else None
                if result:
                    st.markdown("#### Latest result")
                    if result["mode"] == "demo":
                        status_badge("WARNING")
                    else:
                        st.info("Pretrained inference completed; this prediction is not a model safety assessment.")
                    st.caption("INPUT  →  MODEL  →  OUTPUT")
                    flow_input, flow_model, flow_output = st.columns(3)
                    with flow_input, st.container(border=True):
                        st.markdown("**INPUT**")
                        st.code(image_hash[:16] + "…", language=None)
                    with flow_model, st.container(border=True):
                        st.markdown("**MODEL IDENTIFIER**")
                        st.code(result["model_sha256"][:16] + "…", language=None)
                    with flow_output, st.container(border=True):
                        st.markdown("**OUTPUT**")
                        st.write(result["prediction"])
                    if result["confidence"] is not None:
                        st.metric("Model confidence", f"{result['confidence']:.1%}")
                    st.caption(result["note"])
                    st.caption("Audit record saved to SQLite and linked to the preceding record.")
    st.info("Pretrained ResNet-18 is a general ImageNet model, not a domain-specific classifier. First use may require downloading weights.")


elif page == "Audit History":
    page_heading("Audit history", "Review recorded inputs, model identifiers, outputs, timestamps, and hash-chain verification.")
    records = list_audits(DB_PATH)
    chain_valid, chain_message = verify_chain(DB_PATH)
    audit_status = ("PASS" if chain_valid else "HIGH RISK") if records else "WARNING"
    status_badge(audit_status)
    st.write(chain_message)
    if records:
        history = pd.DataFrame(records)
        search_col, mode_col, from_col, to_col = st.columns([2, 1, 1, 1])
        with search_col:
            search = st.text_input("Search audit evidence", placeholder="Record ID, hash, prediction…")
        with mode_col:
            modes = ["All modes", *sorted(history["mode"].dropna().unique().tolist())]
            selected_mode = st.selectbox("Inference mode", modes)
        timestamps = pd.to_datetime(history["timestamp_utc"], utc=True, errors="coerce")
        available_dates = timestamps.dropna().dt.date
        earliest = available_dates.min()
        latest = available_dates.max()
        with from_col:
            start_date = st.date_input("From (UTC)", value=earliest, min_value=earliest, max_value=latest)
        with to_col:
            end_date = st.date_input("To (UTC)", value=latest, min_value=earliest, max_value=latest)
        filtered = history.copy()
        filtered["_timestamp_date"] = timestamps.dt.date
        if selected_mode != "All modes":
            filtered = filtered[filtered["mode"] == selected_mode]
        filtered = filtered[(filtered["_timestamp_date"] >= start_date) & (filtered["_timestamp_date"] <= end_date)]
        if search:
            searchable = history.astype(str).agg(" ".join, axis=1)
            filtered = filtered.loc[filtered.index[searchable.str.contains(search, case=False, regex=False)]]
        st.caption("These records belong to the Inference component. Severity is assessed for the whole hash chain, not separately for each row.")
        m1, m2 = st.columns(2)
        m1.metric("Stored records", len(records))
        m2.metric("Chain verification", "Valid" if chain_valid else "Mismatch")
        display_history = filtered.drop(columns=["_timestamp_date"], errors="ignore").copy()
        for column in ("image_sha256", "model_sha256", "previous_hash", "record_hash"):
            if column in display_history:
                display_history[column] = display_history[column].map(lambda value: f"{value[:12]}…{value[-8:]}" if isinstance(value, str) and len(value) > 24 else value)
        st.dataframe(display_history, use_container_width=True, hide_index=True,
                     column_config={"timestamp_utc": st.column_config.TextColumn("Timestamp (UTC)"),
                                    "confidence": st.column_config.NumberColumn("Confidence", format="%.3f")})
        record_options = {f"Record #{row['id']} · {row['prediction']} · {row['timestamp_utc']}": row for row in records}
        selected_record_label = st.selectbox("Open evidence record", ["Select a record…", *record_options.keys()])
        if selected_record_label != "Select a record…":
            selected_record = record_options[selected_record_label]
            with st.container(border=True):
                st.markdown(f"**Record #{selected_record['id']} · {html.escape(selected_record['prediction'])}**")
                st.write(f"Input SHA-256: `{selected_record['image_sha256']}`")
                st.write(f"Model identifier/hash: `{selected_record['model_sha256']}`")
                st.write(f"Previous hash: `{selected_record['previous_hash']}`")
                st.write(f"Record hash: `{selected_record['record_hash']}`")
        st.download_button("Download all audit records CSV", history.to_csv(index=False).encode("utf-8-sig"), "trustcv_audit_history.csv", "text/csv")
        st.caption(f"Showing {len(filtered)} of {len(history)} records for {start_date} through {end_date} UTC.")
    else:
        show_empty_state("No inference records yet", "The chain is valid and currently empty.", "Go to Inference Audit to create a clearly labelled demo or pretrained record.")


elif page == "Evidence Reports":
    page_heading("Evidence reports", "Package current-session scan findings, model reference metadata, audit records, and limitations.")
    records = list_audits(DB_PATH)
    chain_valid, chain_message = verify_chain(DB_PATH)
    findings = assess(st.session_state.dataset_scan, st.session_state.model_matches,
                      chain_valid if records else None)
    report = {
        "schema": "trustcv-evidence-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "findings": findings,
        "dataset_scan": st.session_state.dataset_scan.to_dict(orient="records") if st.session_state.dataset_scan is not None else None,
        "trusted_model_reference_sha256": get_reference_hash(DB_PATH),
        "audit_chain": {"valid": chain_valid, "message": chain_message},
        "audit_records": records,
        "limitations": [
            "Heuristic dataset checks do not prove the absence of poisoned, mislabeled, out-of-distribution, or trigger samples.",
            "A stored reference hash is meaningful only if obtained through a secure trusted process.",
            "The audit hash chain is tamper-evident, not digitally signed; a party able to rewrite the database and recompute the chain can replace it.",
            "Demo mode is not a real prediction. Pretrained mode uses ImageNet ResNet-18 when available.",
        ],
    }
    m1, m2, m3 = st.columns(3)
    m1.metric("Findings", len(findings))
    m2.metric("Audit records", len(records))
    m3.metric("Chain check", "Valid" if chain_valid else "Mismatch")
    st.markdown("**Current risk findings**")
    for finding in findings:
        left, right = st.columns([1.2, 5])
        with left:
            status_badge(finding["status"])
        with right:
            st.markdown(f"**{finding['area']}** · {finding['reason']}")
    if st.session_state.dataset_scan is None and not records:
        show_empty_state("Evidence is ready to build", "Run a dataset scan, model comparison, or inference audit to add concrete evidence. Current report will state that checks are missing.")
    st.download_button("EXPORT INTEGRITY REPORT · JSON", json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8"), "trustcv_evidence_report.json", "application/json", type="primary")
    exports = st.columns(2)
    with exports[0]:
        if st.session_state.dataset_scan is not None:
            st.download_button("Download dataset scan CSV", st.session_state.dataset_scan.to_csv(index=False).encode("utf-8-sig"), "trustcv_dataset_scan.csv", "text/csv")
    with exports[1]:
        if records:
            st.download_button("Download audit CSV", pd.DataFrame(records).to_csv(index=False).encode("utf-8-sig"), "trustcv_audit_history.csv", "text/csv")
