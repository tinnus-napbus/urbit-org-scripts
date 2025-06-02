#!/usr/bin/env python3
import os
import re
import sys
import csv
import signal
import shutil
import requests
import concurrent.futures
from pathlib import Path
from urllib.parse import urlparse

# === Help ===
def print_usage():
    print("Usage: ./external_link_checker.py <docs-directory> [--csv <output.csv>] [--quiet]\n")
    print("Options:")
    print("  --csv <output.csv>     Write results to CSV file")
    print("  --quiet                Suppress progress output")
    print("  --help                 Show this help message and exit")

# === Patterns ===
EXTERNAL_LINK_PATTERN = re.compile(r'(?<!\!)\[.*?\]\((https?://[^)]+)\)')

# === Utilities ===
def collect_markdown_files(base_dir):
    markdown_files = []
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".md"):
                markdown_files.append(Path(root) / file)
    return markdown_files

def extract_external_links(file_path):
    links = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                for match in EXTERNAL_LINK_PATTERN.findall(line):
                    links.append(match)
    except Exception:
        print(f"Warning: could not read file {file_path}", file=sys.stderr)
    return links

def check_link(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/113.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.head(url, allow_redirects=True, timeout=5, headers=headers)
        if response.status_code == 405:
            response = requests.get(url, allow_redirects=True, timeout=5, headers=headers)
        if response.status_code >= 400:
            return url, False, response.status_code
        return url, True, response.status_code
    except requests.RequestException:
        return url, False, None

def print_progress(index, total, link, quiet):
    if quiet:
        return
    width = shutil.get_terminal_size((80, 20)).columns
    bar_width = 30
    bar_filled = int(bar_width * index / total)
    bar = f"[{'=' * bar_filled}{' ' * (bar_width - bar_filled)}]"
    percent = int(100 * index / total)
    prefix = f"{bar} {percent:3d}% ({index}/{total})"
    link_space = width - len(prefix) - 2
    trimmed_link = (link[:link_space - 3] + '...') if len(link) > link_space else link.ljust(link_space)
    print(f"\r{prefix} {trimmed_link}", end='', flush=True)

# === Main ===
def main():
    if len(sys.argv) < 2 or "--help" in sys.argv:
        print_usage()
        sys.exit(0)

    base_dir = Path(sys.argv[1]).resolve()
    if not base_dir.is_dir():
        print(f"Error: {base_dir} is not a directory")
        sys.exit(1)

    csv_output = None
    quiet = "--quiet" in sys.argv
    if "--csv" in sys.argv:
        csv_index = sys.argv.index("--csv")
        if len(sys.argv) > csv_index + 1:
            csv_output = sys.argv[csv_index + 1]
        else:
            print("Error: Missing filename after --csv")
            sys.exit(1)

    print(f"🔍 Scanning Markdown files in: {base_dir}\n")

    markdown_files = collect_markdown_files(base_dir)
    all_links = []
    for md_file in markdown_files:
        links = extract_external_links(md_file)
        for link in links:
            all_links.append((md_file, link))

    total = len(all_links)
    checked = [None] * total
    broken_links = []

    def worker(index_link):
        i, (md_file, link) = index_link
        url, ok, status = check_link(link)
        checked[i] = (md_file, link, ok, status)
        return i, link

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(worker, (i, item)): i for i, item in enumerate(all_links)}
        for count, future in enumerate(concurrent.futures.as_completed(futures), 1):
            i, link = future.result()
            print_progress(count, total, link, quiet)

    if not quiet:
        print()

    for md_file, link, ok, status in checked:
        if not ok:
            broken_links.append((str(md_file.relative_to(base_dir)), link, status))

    if csv_output:
        with open(csv_output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["source_file", "broken_link", "http_status"])
            for item in broken_links:
                writer.writerow(item)
        print(f"✅ CSV report written to: {csv_output}")
    else:
        if broken_links:
            print("❌ Broken External Links:\n")
            for source_file, link, status in broken_links:
                print(f"- In '{source_file}': {link} (status: {status})")
        else:
            print("✅ No broken external links found.")

if __name__ == "__main__":
    main()

