## Useful scripts for the Urbit Foundation.

Mostly related to docs management

### internal-link-checker.py

Check for broken internal links & anchor links, suggest fuzzily-matched corrections.

#### Requirements

Python libs:
- `rapidfuzz`

#### Usage

Print a report of broken links & anchor links to the terminal:

```sh
internal-link-checker.py /path/to/docs/content
```

Output to a csv file instead:

```sh
internal-link-checker.py /path/to/docs/content --csv report.csv
```

Interactive mode:

```sh
internal-link-checker.py /path/to/docs/content --interactive
```

Interactive mode lets you do one of the following for each of the broken links or anchors detected:

1. choose one of the suggestions to apply it.
2. Flag the link as BROKEN_ANCHOR or BROKEN_LINK depending what the issue is.
3. skip

When you flag links, it's added as tooltip-style syntax, so `[foo](/bad/link)` becomes `[foo](/bad/link "BROKEN_LINK")`. You can then `vim $(grep -riE "BROKEN_LINK|BROKEN_ANCHOR")` or w/e and fix them manually.

---

### external-link-checker.py

Print a report of broken external links

#### Usage

Check external links, print report to terminal:

```sh
external-link-checker.py /path/to/docs/content
```

Output to a csv file instead:

```sh
external-link-checker.py /path/to/docs/content --csv report.csv
```

The --quiet flag will suppress the progress bar etc.

---
