from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class AssetReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del tag
        attributes = dict(attrs)
        for name in ("href", "src"):
            if attributes.get(name):
                self.references.append(attributes[name] or "")


def test_static_site_local_references_exist() -> None:
    for html_file in sorted((REPOSITORY_ROOT / "docs").glob("*.html")):
        parser = AssetReferenceParser()
        parser.feed(html_file.read_text(encoding="utf-8"))

        for reference in parser.references:
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            assert (html_file.parent / parsed.path).is_file(), (
                f"{html_file.relative_to(REPOSITORY_ROOT)} references missing "
                f"file {reference!r}"
            )
