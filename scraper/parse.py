from typing import List, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def _extract_chunks(soup: BeautifulSoup) -> List[dict]:
    body = soup.body or soup
    elements = body.find_all(["h1", "h2", "h3", "p", "li"], recursive=True)
    sections = []
    current_heading = None

    for el in elements:
        name = el.name.lower()
        if name in ("h1", "h2", "h3"):
            heading = el.get_text(" ", strip=True)
            if heading:
                current_heading = heading
                sections.append({"heading": current_heading, "parts": []})
            continue

        text = el.get_text(" ", strip=True)
        if len(text) < 20:
            continue
        if current_heading is None:
            current_heading = "Overview"
            sections.append({"heading": current_heading, "parts": []})
        sections[-1]["parts"].append(text)

    chunks = []
    order = 0
    for section in sections:
        text = "\n".join(section["parts"]).strip()
        if len(text) < 20:
            continue
        chunks.append({"heading": section["heading"], "order": order, "text": text})
        order += 1
    return chunks


def parse_html(html: str, base_url: str) -> Tuple[str, List[dict], List[str]]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else ""

    out_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        if href.lower().startswith(("javascript:", "mailto:", "tel:")):
            continue
        out_links.append(urljoin(base_url, href))

    seen = set()
    unique_links = []
    for link in out_links:
        if link not in seen:
            unique_links.append(link)
            seen.add(link)

    chunks = _extract_chunks(soup)
    return title, chunks, unique_links
