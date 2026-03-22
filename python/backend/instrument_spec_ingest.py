import html
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class SourcePayload:
    source: str
    source_kind: str
    content_type: str
    text: str


def _convert_to_ns(value: float, unit: str) -> float:
    unit_l = str(unit).strip().lower()
    scale = {
        "ps": 1e-3,
        "ns": 1.0,
        "us": 1e3,
        "ms": 1e6,
        "s": 1e9,
    }.get(unit_l)
    if scale is None:
        raise ValueError(f"Unsupported time unit: {unit}")
    return float(value) * scale


def _strip_html(raw_html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw_html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>|</div>|</li>|</tr>|</h\d>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _extract_pdf_text(payload: bytes, max_pages: int = 16) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        raise RuntimeError("PDF extraction requires the 'pypdf' package.") from exc

    import io

    reader = PdfReader(io.BytesIO(payload))
    pages = []
    for page in reader.pages[: max(int(max_pages), 1)]:
        with_text = page.extract_text() or ""
        pages.append(with_text)
    return "\n\n".join(pages).strip()


def load_instrument_source(source: str, max_chars: int = 24000, max_pages: int = 16) -> SourcePayload:
    source = str(source).strip()
    if not source:
        raise ValueError("Source cannot be empty.")

    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in {"http", "https"}:
        req = urllib.request.Request(source, headers={"User-Agent": "HILIGHTer-DigitalTwin/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            content_type = str(resp.headers.get("Content-Type", "application/octet-stream")).lower()
            payload = resp.read()
        if "pdf" in content_type or source.lower().endswith(".pdf"):
            text = _extract_pdf_text(payload, max_pages=max_pages)
            kind = "pdf_url"
            ctype = "application/pdf"
        else:
            text = _strip_html(payload.decode("utf-8", errors="ignore"))
            kind = "webpage"
            ctype = content_type
    else:
        if not os.path.exists(source):
            raise FileNotFoundError(source)
        ext = os.path.splitext(source)[1].lower()
        if ext == ".pdf":
            with open(source, "rb") as handle:
                text = _extract_pdf_text(handle.read(), max_pages=max_pages)
            kind = "pdf_file"
            ctype = "application/pdf"
        elif ext in {".html", ".htm"}:
            with open(source, "r", encoding="utf-8", errors="ignore") as handle:
                text = _strip_html(handle.read())
            kind = "html_file"
            ctype = "text/html"
        else:
            with open(source, "r", encoding="utf-8", errors="ignore") as handle:
                text = handle.read()
            text = re.sub(r"\r\n?", "\n", text).strip()
            kind = "text_file"
            ctype = "text/plain"

    text = re.sub(r"\n{3,}", "\n\n", text)
    if max_chars > 0:
        text = text[:max_chars]
    return SourcePayload(source=source, source_kind=kind, content_type=ctype, text=text)


def infer_instrument_profile_patch(text: str) -> Dict[str, Any]:
    text = str(text or "")
    lowered = text.lower()
    patch: Dict[str, Any] = {}
    evidence: Dict[str, Any] = {}

    rep_rate = re.search(r"(?i)(?:repetition rate|rep rate|laser repetition rate|frequency)\D{0,20}([0-9]+(?:\.[0-9]+)?)\s*(hz|khz|mhz|ghz)", text)
    if rep_rate:
        value = float(rep_rate.group(1))
        unit = rep_rate.group(2).lower()
        hz = value * {"hz": 1.0, "khz": 1e3, "mhz": 1e6, "ghz": 1e9}[unit]
        if hz > 0:
            period_ns = 1e9 / hz
            patch["period"] = period_ns
            evidence["repetition_rate"] = {"value": value, "unit": unit, "derived_period_ns": period_ns}

    if "period" not in patch:
        period_match = re.search(r"(?i)(?:period|repetition period|measurement window|acquisition window|time window)\D{0,20}([0-9]+(?:\.[0-9]+)?)\s*(ps|ns|us|ms|s)", text)
        if period_match:
            period_ns = _convert_to_ns(float(period_match.group(1)), period_match.group(2))
            patch["period"] = period_ns
            evidence["period"] = {"value_ns": period_ns}

    bins_match = re.search(r"(?i)\b([0-9]{1,4})\s*(?:bins|time bins|channels|gates)\b", text)
    if bins_match:
        bins = max(int(bins_match.group(1)), 1)
        evidence["bins_or_gates"] = bins
        if "period" in patch and bins >= 2:
            patch["gate_type"] = "equal"
            patch["gate_edges"] = np.linspace(0.0, float(patch["period"]), bins + 1).tolist()

    jitter_match = re.search(r"(?i)(?:timing jitter|jitter|transit time spread|tts)\D{0,20}([0-9]+(?:\.[0-9]+)?)\s*(ps|ns)", text)
    if jitter_match:
        jitter_ps = _convert_to_ns(float(jitter_match.group(1)), jitter_match.group(2)) * 1000.0
        patch["timing_jitter"] = jitter_ps
        evidence["timing_jitter_ps"] = jitter_ps

    deadtime_match = re.search(r"(?i)(?:dead\s*time|deadtime)\D{0,20}([0-9]+(?:\.[0-9]+)?)\s*(ps|ns|us)", text)
    if deadtime_match:
        deadtime_ns = _convert_to_ns(float(deadtime_match.group(1)), deadtime_match.group(2))
        patch["detector_deadtime"] = deadtime_ns
        evidence["detector_deadtime_ns"] = deadtime_ns

    if re.search(r"(?i)\b(single[- ]hit|first[- ]hit)\b", text):
        patch["b_multihit_mode"] = False
        patch["event_multihit_capacity"] = 1
        evidence["multihit"] = "single-hit"
    elif re.search(r"(?i)\b(multi[- ]hit|multihit)\b", text):
        patch["b_multihit_mode"] = True
        evidence["multihit"] = "multihit"

    if re.search(r"(?i)\btcspc\b", lowered):
        patch.setdefault("gate_type", "equal")
        evidence["detector_style"] = "tcspc"

    if re.search(r"(?i)\b(dirac|delta pulse|ideal pulse)\b", lowered):
        patch["irf_profile"] = "ideal (dirac)"
        patch["irf_fwhm"] = 0.0
        evidence["laser_profile"] = "ideal (dirac)"
    elif re.search(r"(?i)\b(rectangular|square pulse)\b", lowered):
        patch["irf_profile"] = "rectangular"
        evidence["laser_profile"] = "rectangular"
    elif re.search(r"(?i)\b(gaussian)\b", lowered):
        patch["irf_profile"] = "gaussian"
        evidence["laser_profile"] = "gaussian"

    width_match = re.search(r"(?i)(?:fwhm|pulse width|laser width|irf width)\D{0,20}([0-9]+(?:\.[0-9]+)?)\s*(ps|ns|us)", text)
    if width_match:
        patch["irf_fwhm"] = _convert_to_ns(float(width_match.group(1)), width_match.group(2))
        evidence["irf_fwhm_ns"] = patch["irf_fwhm"]

    pos_match = re.search(r"(?i)(?:start time|position|delay|offset)\D{0,20}([0-9]+(?:\.[0-9]+)?)\s*(ps|ns|us)", text)
    if pos_match:
        patch["irf_position"] = _convert_to_ns(float(pos_match.group(1)), pos_match.group(2))
        evidence["irf_position_ns"] = patch["irf_position"]

    return {"patch": patch, "evidence": evidence}

