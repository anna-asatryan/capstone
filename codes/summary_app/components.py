from __future__ import annotations

import html
import html
from pathlib import Path
from typing import Iterable

import streamlit as st


def load_css() -> None:
    css_path = Path(__file__).resolve().parent / "assets" / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def hero(title: str, subtitle: str, pills: Iterable[str] | None = None) -> None:
    pill_html = ""
    if pills:
        pill_html = "<div class='hero-strip'>" + "".join(f"<span class='pill'>{html.escape(str(p))}</span>" for p in pills) + "</div>"
    st.markdown(
        f"<div class='hero'>"
        f"<div class='hero-title'>{html.escape(title)}</div>"
        f"<p class='hero-subtitle'>{html.escape(subtitle)}</p>"
        f"{pill_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def metric_cards(cards: list[dict]) -> None:
    html_cards = []
    for c in cards:
        html_cards.append(
            f"<div class='metric-card'>"
            f"<div class='metric-label'>{html.escape(str(c.get('label', '')))}</div>"
            f"<div class='metric-value'>{html.escape(str(c.get('value', '')))}</div>"
            f"<div class='metric-note'>{html.escape(str(c.get('note', '')))}</div>"
            f"</div>"
        )
    st.markdown("<div class='metric-grid'>" + "".join(html_cards) + "</div>", unsafe_allow_html=True)


def finding(text: str) -> None:
    st.markdown(f"<div class='finding-box'>{text}</div>", unsafe_allow_html=True)


def warning(text: str) -> None:
    st.markdown(f"<div class='warning-box'>{text}</div>", unsafe_allow_html=True)


def section_kicker(text: str) -> None:
    st.markdown(f"<div class='section-kicker'>{html.escape(text)}</div>", unsafe_allow_html=True)


def small_note(text: str) -> None:
    st.markdown(f"<div class='small-note'>{html.escape(text)}</div>", unsafe_allow_html=True)


def case_card(title: str, meta: str) -> None:
    st.markdown(
        f"<div class='case-card'>"
        f"<div class='case-title'>{html.escape(title)}</div>"
        f"<div class='case-meta'>{html.escape(meta)}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
