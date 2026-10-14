import collections
import json
from pathlib import Path


CONTENT_DIR = Path(__file__).resolve().parents[1] / "src" / "content" / "downloaders"
MAIN_PLATFORMS = ("YouTube", "TikTok", "Instagram", "Facebook", "X", "LinkedIn")


def validate():
    pages = sorted(CONTENT_DIR.glob("*.md"))
    if len(pages) != 100:
        raise ValueError(f"Expected 100 Markdown pages, found {len(pages)}.")

    counts = collections.Counter()
    for page in pages:
        text = page.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) != 3:
            raise ValueError(f"Missing frontmatter in {page.name}.")
        frontmatter, body = parts[1], parts[2]
        fields = {line.split(":", 1)[0] for line in frontmatter.splitlines() if ":" in line}
        if not {"title", "platform", "description", "keywords"}.issubset(fields):
            raise ValueError(f"Missing required frontmatter in {page.name}.")
        platform = next(line.split('"')[1] for line in frontmatter.splitlines() if line.startswith("platform:"))
        description = json.loads(next(line.split(": ", 1)[1] for line in frontmatter.splitlines() if line.startswith("description:")))
        if len(description) >= 160:
            raise ValueError(f"Description is too long in {page.name}.")
        if len([line for line in body.splitlines() if line.startswith(("1. ", "2. ", "3. "))]) != 3:
            raise ValueError(f"Expected three steps in {page.name}.")
        rows = [line for line in body.splitlines() if line.startswith("| ") and not line.startswith("| ---") and line != "| Tool | Best use |"]
        if len(rows) != 3:
            raise ValueError(f"Expected three tool rows in {page.name}.")
        if body.count("### ") != 3:
            raise ValueError(f"Expected three FAQ entries in {page.name}.")
        schema = json.loads(text.split('<script type="application/ld+json">', 1)[1].split("</script>", 1)[0])
        if schema.get("@type") != "FAQPage" or len(schema.get("mainEntity", [])) != 3:
            raise ValueError(f"Invalid FAQPage schema in {page.name}.")
        counts[platform] += 1

    if any(counts[platform] < 7 for platform in MAIN_PLATFORMS):
        raise ValueError(f"A homepage platform has fewer than seven guides: {dict(counts)}")
    if any(count < 5 for count in counts.values()):
        raise ValueError(f"A platform cannot provide four related guides: {dict(counts)}")
    print(f"Validated {len(pages)} guides: {dict(counts)}")


if __name__ == "__main__":
    validate()
