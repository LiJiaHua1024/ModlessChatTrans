#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Extract gettext messages and merge translation catalogs.

This script is intentionally limited to template/catalog maintenance:
it updates ``i18n/translations.pot`` and merges existing ``i18n/*.po``
files without generating translations. New or changed source references
are reflected in the POT, and newly introduced PO entries keep an empty
``msgstr``.

Run from the project root with:

    uv run --group tools python tools/update_translations.py
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from babel.messages import Catalog
from babel.messages.catalog import Message
from babel.messages.extract import extract_from_dir
from babel.messages.frontend import parse_mapping_cfg
from babel.messages.pofile import read_po, write_po

PROJECT_ROOT = Path(__file__).resolve().parents[1]
I18N_DIR = PROJECT_ROOT / "i18n"
SOURCE_DIR = PROJECT_ROOT / "src"
BABEL_CONFIG = I18N_DIR / "babel.cfg"
POT_FILE = I18N_DIR / "translations.pot"
DOMAIN = "translations"
LINE_WIDTH = 76
VOLATILE_POT_HEADERS = {"POT-Creation-Date"}
VOLATILE_PO_HEADERS = {"PO-Revision-Date", "Last-Translator", "Language-Team"}


@dataclass(frozen=True)
class ExtractedMessage:
    """Deduplicated message extracted from source files."""

    locations: tuple[tuple[str, int], ...]
    comments: tuple[str, ...]


def message_key(message: Message) -> tuple[str | None, object]:
    """Return the catalog key used by gettext for a message."""

    return message.context, message.id


def normalize_path(path: str) -> str:
    """Normalize Babel's platform-specific paths to forward slashes."""

    return path.replace("\\", "/")


def load_method_map(config_file: Path):
    """Load the Babel extraction mapping file."""

    with config_file.open("r", encoding="utf-8") as file_obj:
        return parse_mapping_cfg(file_obj, filename=str(config_file))


def extract_messages(source_dir: Path, config_file: Path) -> dict[tuple[str | None, object], ExtractedMessage]:
    """Extract messages and deduplicate identical references."""

    method_map, options_map = load_method_map(config_file)
    messages: dict[tuple[str | None, object], list[tuple[tuple[str, int], str]]] = {}

    for filename, lineno, message, comments, _context in extract_from_dir(
        source_dir,
        method_map=method_map,
        options_map=options_map,
        strip_comment_tags=False,
    ):
        key = (_context, message)
        location = (normalize_path(filename), lineno)
        comment_list = messages.setdefault(key, [])
        comment_list.append((location, "\n".join(comments)))

    deduplicated: dict[tuple[str | None, object], ExtractedMessage] = {}
    for key, refs in messages.items():
        locations: list[tuple[str, int]] = []
        comments: list[str] = []
        for location, comment in refs:
            if location not in locations:
                locations.append(location)
            if comment and comment not in comments:
                comments.append(comment)
        deduplicated[key] = ExtractedMessage(tuple(locations), tuple(comments))

    return deduplicated


def first_extraction_order(extracted: dict[tuple[str | None, object], ExtractedMessage]) -> list[tuple[str | None, object]]:
    """Return message keys in stable first-seen extraction order."""

    order: list[tuple[str | None, object]] = []
    seen: set[tuple[str | None, str]] = set()

    method_map, options_map = load_method_map(BABEL_CONFIG)
    for filename, _lineno, message, _comments, context in extract_from_dir(
        SOURCE_DIR,
        method_map=method_map,
        options_map=options_map,
        strip_comment_tags=False,
    ):
        key = (context, message)
        marker = (context, str(message))
        if marker not in seen:
            seen.add(marker)
            order.append(key)

    # Keep any extracted messages that were not emitted by the second pass.
    for key in extracted:
        marker = (key[0], str(key[1]))
        if marker not in seen:
            order.append(key)
            seen.add(marker)

    return order


def copy_existing_header(target: Catalog, source: Catalog) -> None:
    """Copy stable header fields from an existing catalog."""

    target.project = source.project or target.project
    target.version = source.version or target.version
    target.copyright_holder = source.copyright_holder or target.copyright_holder
    target.msgid_bugs_address = source.msgid_bugs_address or target.msgid_bugs_address
    target.header_comment = source.header_comment or target.header_comment
    target.creation_date = source.creation_date or target.creation_date


def build_pot_catalog(existing_pot: Catalog | None, extracted: dict[tuple[str | None, object], ExtractedMessage]) -> Catalog:
    """Build a POT that preserves existing message order when possible."""

    catalog = Catalog(
        domain=DOMAIN,
        project=(existing_pot.project if existing_pot else None) or "PROJECT",
        version=(existing_pot.version if existing_pot else None) or "VERSION",
        charset="utf-8",
        creation_date=(existing_pot.creation_date if existing_pot else None),
    )
    if existing_pot:
        copy_existing_header(catalog, existing_pot)

    emitted: set[tuple[str | None, str]] = set()
    if existing_pot:
        for message in existing_pot:
            key = message_key(message)
            if key not in extracted:
                continue
            info = extracted[key]
            catalog.add(
                id=message.id,
                string="",
                locations=info.locations,
                auto_comments=list(info.comments),
                context=message.context,
                flags=list(message.flags),
            )
            emitted.add((message.context, str(message.id)))

    for key in first_extraction_order(extracted):
        marker = (key[0], str(key[1]))
        if marker in emitted:
            continue
        info = extracted[key]
        catalog.add(
            id=key[1],
            string="",
            locations=info.locations,
            auto_comments=list(info.comments),
            context=key[0],
        )

    return catalog


def render_catalog(catalog: Catalog, omit_header: bool = False) -> str:
    """Render a catalog to text with stable formatting."""

    buffer = tempfile.TemporaryFile()
    try:
        write_po(
            buffer,
            catalog,
            width=LINE_WIDTH,
            sort_output=False,
            sort_by_file=False,
            omit_header=omit_header,
        )
        buffer.seek(0)
        return buffer.read().decode("utf-8")
    finally:
        buffer.close()


def append_new_po_entries(po_file: Path, new_pot: Catalog, dry_run: bool = False) -> bool:
    """Append only new blank entries to an existing PO file.

    Existing translations, comments, flags, and source references are preserved
    byte-for-byte. This keeps repeated runs quiet: once a msgid exists in a PO,
    the script will not rewrite that entry just to refresh references.
    """

    existing_po = read_po(po_file.open("r", encoding="utf-8"))
    existing_keys = {message_key(message) for message in existing_po}
    additions = [message for message in new_pot if message_key(message) not in existing_keys]

    if not additions:
        return False

    additions_catalog = Catalog(domain=DOMAIN, charset="utf-8")
    for message in additions:
        additions_catalog.add(
            id=message.id,
            string="",
            locations=message.locations,
            flags=message.flags,
            auto_comments=message.auto_comments,
            user_comments=message.user_comments,
            previous_id=message.previous_id,
            context=message.context,
        )

    rendered_additions = render_catalog(additions_catalog, omit_header=True).lstrip()
    existing_text = po_file.read_text(encoding="utf-8")
    line_ending = "\r\n" if "\r\n" in existing_text else "\n"
    separator = line_ending * 2
    new_text = existing_text.rstrip() + separator + rendered_additions

    if dry_run:
        print(f"Would update: {po_file.relative_to(PROJECT_ROOT)}")
        return True

    po_file.write_text(new_text, encoding="utf-8", newline="")
    print(f"Updated: {po_file.relative_to(PROJECT_ROOT)}")
    return True


def normalize_text_for_compare(text: str, volatile_headers: set[str]) -> str:
    """Normalize text while ignoring headers that naturally change."""

    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    filtered: list[str] = []
    in_header = False
    header_key: str | None = None

    for line in lines:
        if line.startswith("msgid \"\""):
            in_header = True
            header_key = None
        elif in_header and line.startswith("msgstr "):
            in_header = False
            header_key = None

        if in_header and line.startswith('"') and ": " in line:
            header_key = line.split(":", 1)[0].strip('"')
            if header_key in volatile_headers:
                continue

        if not line.rstrip():
            filtered.append("")
        else:
            filtered.append(line.rstrip())

    return "\n".join(filtered).rstrip() + "\n"


def write_if_changed(path: Path, content: str, volatile_headers: set[str], dry_run: bool = False) -> bool:
    """Write ``content`` only when normalized content differs."""

    normalized = normalize_text_for_compare(content, volatile_headers)
    if path.exists():
        current = path.read_text(encoding="utf-8")
        current_normalized = normalize_text_for_compare(current, volatile_headers)
        if current_normalized == normalized:
            return False

    if dry_run:
        print(f"Would update: {path.relative_to(PROJECT_ROOT)}")
        return True

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as temp_file:
        temp_file.write(normalized)
        temp_path = Path(temp_file.name)
    shutil.move(str(temp_path), path)
    print(f"Updated: {path.relative_to(PROJECT_ROOT)}")
    return True


def update_pot(extracted: dict[tuple[str | None, object], ExtractedMessage], dry_run: bool = False) -> bool:
    """Update the POT file from extracted messages."""

    existing_pot = read_po(POT_FILE.open("r", encoding="utf-8")) if POT_FILE.exists() else None
    new_pot = build_pot_catalog(existing_pot, extracted)
    return write_if_changed(POT_FILE, render_catalog(new_pot), VOLATILE_POT_HEADERS, dry_run=dry_run)


def update_po_files(new_pot: Catalog, dry_run: bool = False) -> bool:
    """Append new blank entries to all existing PO files."""

    changed = False
    for po_file in sorted(I18N_DIR.glob("*.po")):
        if po_file.name == POT_FILE.name:
            continue
        changed = append_new_po_entries(po_file, new_pot, dry_run=dry_run) or changed
    return changed


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Extract gettext messages and merge PO catalogs.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print files that would change without writing them.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with status 1 when files would change.",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    """Run the i18n extraction and merge workflow."""

    args = parse_args(sys.argv[1:] if argv is None else argv)

    if not BABEL_CONFIG.is_file():
        print(f"Error: Babel config not found: {BABEL_CONFIG}", file=sys.stderr)
        return 2
    if not SOURCE_DIR.is_dir():
        print(f"Error: source directory not found: {SOURCE_DIR}", file=sys.stderr)
        return 2

    extracted = extract_messages(SOURCE_DIR, BABEL_CONFIG)
    pot_changed = update_pot(extracted, dry_run=args.dry_run)
    new_pot = build_pot_catalog(read_po(POT_FILE.open("r", encoding="utf-8")) if POT_FILE.exists() else None, extracted)
    po_changed = update_po_files(new_pot, dry_run=args.dry_run)

    if not pot_changed and not po_changed:
        print("No i18n catalog changes needed.")
        return 0

    print("i18n extraction and merge complete.")
    if args.check:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
