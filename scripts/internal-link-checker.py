#!/usr/bin/env python3
import os
import re
import sys
import csv
from pathlib import Path
from rapidfuzz import process, fuzz

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"

# === Help ===
def print_usage():
    print("Usage: ./check_links.py <docs-directory> [--csv <output.csv>] [--interactive]\n")
    print("Options:")
    print("  --csv <output.csv>     Write results to CSV file")
    print("  --interactive          Prompt interactively to fix broken links/anchors")
    print("  --help                 Show this help message and exit")

# === Patterns ===
LINK_PATTERN = re.compile(r'(?<!\!)\[.*?\]\((.*?)\)')
HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+?)(?:\s+\{#([a-zA-Z0-9\-_]+)\})?\s*$')
HTML_ANCHOR_PATTERN = re.compile(r'<a\s+[^>]*id=["\']([a-zA-Z0-9\-_]+)["\'][^>]*>', re.IGNORECASE)

# === Utilities ===
def collect_markdown_files(base_dir):
    markdown_files = []
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".md"):
                full_path = Path(root) / file
                relative_path = full_path.relative_to(base_dir)
                markdown_files.append(str(relative_path).replace("\\", "/"))
    return markdown_files

def extract_links_from_markdown(file_path):
    links = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                for match in LINK_PATTERN.findall(line):
                    if not match.startswith(('http://', 'https://', '/', '#')):
                        links.append(match)
    except Exception:
        print(f"Warning: could not read file {file_path}", file=sys.stderr)
    return links

def strip_fragment(link):
    return link.split('#')[0]

def extract_fragment(link):
    parts = link.split('#', 1)
    return parts[1] if len(parts) == 2 else None

def generate_anchor(text):
    text = text.strip().lower().replace(' ', '-')
    text = re.sub(r'[^a-z0-9\-]', '', text)
    return text

def extract_anchors_from_file(filepath):
    anchors = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                heading_match = HEADING_PATTERN.match(line)
                if heading_match:
                    _, heading_text, custom_anchor = heading_match.groups()
                    if custom_anchor:
                        anchors.add(custom_anchor)
                    else:
                        anchors.add(generate_anchor(heading_text))
                for html_anchor in HTML_ANCHOR_PATTERN.findall(line):
                    anchors.add(html_anchor)
    except Exception:
        print(f"Warning: could not read file {filepath}", file=sys.stderr)
    return anchors

def suggest_fixes(broken_link, valid_paths, from_file, base_path):
    from_path = (base_path / from_file).parent
    link_path = strip_fragment(broken_link)
    fragment = extract_fragment(broken_link)
    suggestions = process.extract(link_path, valid_paths, scorer=fuzz.ratio, limit=3)
    rel_suggestions = []
    for candidate, score, _ in suggestions:
        abs_candidate = base_path / candidate
        rel_path = os.path.relpath(abs_candidate, from_path).replace("\\", "/")
        if fragment:
            anchors = extract_anchors_from_file(abs_candidate)
            if anchors:
                best_match = process.extractOne(fragment, anchors, scorer=fuzz.ratio)
                if best_match:
                    rel_path += f"#{best_match[0]}"
        rel_suggestions.append((rel_path, score))
    return rel_suggestions

# === Broken Link Detection ===
def find_broken_files(base_path, valid_paths):
    broken = []
    all_links = {}

    for md_file in valid_paths:
        file_path = base_path / md_file
        links = extract_links_from_markdown(file_path)

        for link in links:
            link_no_anchor = strip_fragment(link)
            fragment = extract_fragment(link)

            try:
                resolved_path = (file_path.parent / link_no_anchor).resolve()
                relative_resolved = resolved_path.relative_to(base_path)
                normalized = str(relative_resolved).replace("\\", "/")
            except Exception:
                resolved_path = None
                normalized = None

            is_valid = False
            if normalized in valid_paths:
                is_valid = True
            elif resolved_path and resolved_path.is_dir():
                if (resolved_path / "README.md").exists():
                    is_valid = True
                    resolved_path = resolved_path / "README.md"
                    normalized = str(resolved_path.relative_to(base_path)).replace("\\", "/")
            elif resolved_path and resolved_path.exists():
                is_valid = True

            if is_valid:
                all_links[(md_file, link)] = resolved_path
            else:
                suggestions = suggest_fixes(link, valid_paths, md_file, base_path)
                broken.append((md_file, link, "broken_link", suggestions))

    return broken, all_links

def find_broken_anchors(all_links, base_path):
    broken = []
    for (source_file, full_link), resolved_path in all_links.items():
        fragment = extract_fragment(full_link)
        if not fragment:
            continue
        anchors = extract_anchors_from_file(resolved_path)
        if fragment not in anchors:
            suggestions = process.extract(fragment, anchors, scorer=fuzz.ratio, limit=3)
            suggestions = [(f"#{anchor}", score, _) for anchor, score, _ in suggestions]
            broken.append((source_file, full_link, "broken_anchor", suggestions))
    return broken

# === CSV Output ===
def write_csv(output_path, broken_items):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        max_suggestions = max((len(s[3]) for s in broken_items), default=0)
        headers = ["source_file", "broken_link", "issue_type"] + [f"suggestion_{i+1}" for i in range(max_suggestions)]
        writer.writerow(headers)
        for source_file, broken_link, issue_type, suggestions in broken_items:
            suggestion_texts = [text for text, *_ in suggestions]
            row = [source_file, broken_link, issue_type] + suggestion_texts
            writer.writerow(row)

# === Interactive Fix ===
def prompt_and_fix_interactively(base_path, issues):
    try:
        for source_file, broken_link, issue_type, suggestions in issues:
            print(f"\n🔧 {BOLD}File:{RESET} {BLUE}{source_file}{RESET}")
            label = "Broken anchor:" if issue_type == "broken_anchor" else "Broken link:"
            color = MAGENTA if issue_type == "broken_anchor" else YELLOW
            print(f"   {label} {color}{broken_link}{RESET}")

            if not suggestions:
                print("   No suggestions available. Skipping.")
                continue

            print("   Suggestions:")
            for idx, (sugg, score, *_) in enumerate(suggestions, 1):
                print(f"     {idx}. {CYAN}{sugg}{RESET} ({score:.1f}%)")

            while True:
                choice = input("   Choose a fix (1-3), S to skip, or F to flag as broken: ").strip().lower()
                if choice in {"s", "f", "1", "2", "3"}:
                    break

            if choice == "s":
                continue

            full_path = base_path / source_file
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if choice == "f":
                    marker = "BROKEN_ANCHOR" if issue_type == "broken_anchor" else "BROKEN_LINK"
                    escaped_link = re.escape(broken_link)
                    new_content = re.sub(rf'(\[([^\]]+?)\]\({escaped_link})(\))', rf'\1 "{marker}"\3', content)
                    print(f"   ⚠️  Link marked as {marker.lower().replace('_', ' ')}.")
                else:
                    replacement = suggestions[int(choice) - 1][0]
                    if issue_type == "broken_anchor":
                        base = strip_fragment(broken_link)
                        fragment = extract_fragment(replacement)
                        replacement = f"{base}#{fragment}" if fragment else base
                    escaped_link = re.escape(broken_link)
                    new_content = re.sub(rf'(\[([^\]]+?)\]\(){escaped_link}(\))', rf'\1{replacement}\3', content)
                    print("   ✅ Link updated.")

                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

            except Exception as e:
                print(f"   ❌ Error editing file: {e}")
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user. Exiting.")

# === Main ===
def main():
    if len(sys.argv) < 2 or "--help" in sys.argv:
        print_usage()
        sys.exit(0)

    base_dir = sys.argv[1]
    if not os.path.isdir(base_dir):
        print(f"Error: {base_dir} is not a directory")
        sys.exit(1)

    csv_output = None
    interactive_mode = "--interactive" in sys.argv
    if "--csv" in sys.argv:
        csv_index = sys.argv.index("--csv")
        if len(sys.argv) > csv_index + 1:
            csv_output = sys.argv[csv_index + 1]
        else:
            print("Error: Missing filename after --csv")
            sys.exit(1)

    print(f"🔍 Scanning Markdown files in: {base_dir}\n")
    base_path = Path(base_dir).resolve()
    valid_paths = collect_markdown_files(base_path)

    broken_files, all_valid_links = find_broken_files(base_path, valid_paths)
    broken_anchors = find_broken_anchors(all_valid_links, base_path)
    all_issues = broken_files + broken_anchors

    if interactive_mode:
        prompt_and_fix_interactively(base_path, all_issues)
        return

    if csv_output:
        write_csv(csv_output, all_issues)
        print(f"✅ CSV report written to: {csv_output}")
        return

    if broken_files:
        print("❌ Broken File Links:\n")
        for source_file, broken_link, _, suggestions in broken_files:
            print(f"🔧 {BOLD}File:{RESET} {BLUE}{source_file}{RESET}")
            print(f"   Broken link: {YELLOW}{broken_link}{RESET}")
            if suggestions:
                print("   Suggestions:")
                for rel_path, score in suggestions:
                    print(f"     • {CYAN}{rel_path}{RESET} ({score:.1f}%)")
            print()
    else:
        print("✅ No broken file links found.\n")

    if broken_anchors:
        print("❌ Broken Anchor Fragments:\n")
        for source_file, full_link, _, suggestions in broken_anchors:
            print(f"🔧 {BOLD}File:{RESET} {BLUE}{source_file}{RESET}")
            print(f"   Broken anchor: {MAGENTA}{full_link}{RESET}")
            if suggestions:
                print("   Suggestions:")
                for anchor, score, _ in suggestions:
                    print(f"     • {MAGENTA}{anchor}{RESET} ({score:.1f}%)")
            print()
    else:
        print("✅ No broken anchor fragments found.")

if __name__ == "__main__":
    main()

