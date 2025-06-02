## Useful scripts for the Urbit Foundation.

Mostly related to docs management

### `link-checker.py`

Check for broken internal links & anchor links, suggest fuzzily-matched corrections.

#### Requirements

Python libs:
- `rapidfuzz`

#### Usage

Print a report of broken links & anchor links to the terminal:

```sh
link-checker.py /path/to/docs/content
```

Output to a csv file instead:

```sh
link-checker.py /path/to/docs/content --csv report.csv
```

Interactive mode:

```sh
link-checker.py /path/to/docs/content --interactive
```

Interactive mode lets you do one of the following for each of the broken links or anchors detected:

1. choose one of the suggestions to apply it.
2. Mark the link as BROKEN_ANCHOR or BROKEN_LINK depending what the issue is. This is added as tooltip-style syntax, so `[foo](/bad/link)` becomes `[foo](/bad/link "BROKEN_LINK")`.
3. skip

You can then `vim $(grep -riE "BROKEN_LINK|BROKEN_ANCHOR")` or w/e and fix them manually.

---
