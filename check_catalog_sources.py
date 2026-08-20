"""
check_catalog_sources.py

Weekly automated check for CardCredit's catalog — runs via GitHub Actions, not manually.

What this actually does, stated plainly rather than oversold: it fetches each card's official
benefits page (the sourceURL already stored in catalog.json), hashes the page content, and
compares that hash to what it saw last week. If the hash changed, it opens a GitHub Issue
flagging that card for a human to look at.

What this does NOT do, and can't reliably do: tell you that a specific new benefit was added.
Detecting "a benefit was added" from a page's raw HTML is a real content-understanding problem,
not something a hash comparison can do. A changed hash could mean a new benefit, a removed one,
a dollar amount update, a typo fix, or something entirely unrelated to benefits (a redesigned
page header, a new promotional banner, etc.). Treat every flagged issue as "worth a look," not
"a new benefit exists here" — the actual catalog.json update still needs a human (or a future
Claude conversation) to read the real page and decide what changed.
"""

import json
import hashlib
import os
import subprocess
import urllib.request

CATALOG_PATH = "catalog.json"
HASHES_PATH = "page-hashes.json"


def fetch_page_hash(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (CardCredit catalog checker)"})
        with urllib.request.urlopen(req, timeout=20) as response:
            content = response.read()
        return hashlib.sha256(content).hexdigest()
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None


def main():
    with open(CATALOG_PATH) as f:
        catalog = json.load(f)

    old_hashes = {}
    if os.path.exists(HASHES_PATH):
        with open(HASHES_PATH) as f:
            old_hashes = json.load(f)

    new_hashes = {}
    changed_cards = []

    for card in catalog:
        card_id = card["id"]
        source_url = card.get("sourceURL")
        if not source_url:
            continue

        new_hash = fetch_page_hash(source_url)
        if new_hash is None:
            if card_id in old_hashes:
                new_hashes[card_id] = old_hashes[card_id]
            continue

        new_hashes[card_id] = new_hash
        old_hash = old_hashes.get(card_id)
        if old_hash is not None and old_hash != new_hash:
            changed_cards.append((card_id, card.get("displayName", card_id), source_url))

    with open(HASHES_PATH, "w") as f:
        json.dump(new_hashes, f, indent=2)

    if changed_cards:
        body_lines = [
            "The following card benefit pages appear to have changed since the last weekly check.",
            "",
            "This only detects that *something* changed on the page — it can't tell whether it's "
            "a new benefit, a removed one, a wording tweak, or something unrelated. Each one needs "
            "a real look before catalog.json gets updated.",
            "",
        ]
        for card_id, display_name, url in changed_cards:
            body_lines.append(f"- **{display_name}** (`{card_id}`) — {url}")

        title = f"Weekly catalog check: {len(changed_cards)} card page(s) changed"
        body = "\n".join(body_lines)

        subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", body],
            check=True,
        )
        print(f"Created issue for {len(changed_cards)} changed card(s).")
    else:
        print("No changes detected this week.")


if __name__ == "__main__":
    main()
