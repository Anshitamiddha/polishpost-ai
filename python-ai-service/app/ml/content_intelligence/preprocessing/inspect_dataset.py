"""Look inside the YouTube metadata CSV before any cleaning or modelling.

This script only reads and reports. It never writes to the CSV, renames
columns, removes missing values or cleans text.

Run it from the python-ai-service folder:

    python app/ml/content_intelligence/preprocessing/inspect_dataset.py
    python app/ml/content_intelligence/preprocessing/inspect_dataset.py path/to/file.csv

With no path, it looks in app/ml/content_intelligence/datasets/raw/.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

import pandas as pd

# This file is in preprocessing/, so two levels up is content_intelligence/.
RAW_DATA_FOLDER = Path(__file__).resolve().parents[1] / "datasets" / "raw"

RECORDS_TO_PREVIEW = 5
MAX_CHARACTERS_PER_VALUE = 150  # long text is shortened on screen only
MAX_CATEGORY_ROWS_SHOWN = 20
EXAMPLES_SHOWN = 3

# Search-result snippets are cut short. A full description usually is not.
SNIPPET_MAX_CHARACTERS = 200
ELLIPSIS_SHARE_THAT_SUGGESTS_TRUNCATION = 0.10
ENDS_WITH_ELLIPSIS_PATTERN = r"(?:\.\.\.|…)\s*$"

# A hashtag is "#" plus a letter ("#shorts" counts, "#1" does not), and it starts the
# text or follows a space or "(". This skips "#" inside links such as page.html#top.
# The dataset writes line breaks as the two characters \n, so that counts as a space too.
HASHTAG_PATTERN = r"(?:^|[\s(]|\\n)#[^\W\d]\w*"

# Cells that fill the tags column without holding real tags.
PLACEHOLDER_TAG_VALUES = {"[none]", "none", "null", "nan", "n/a"}

# The terms we expect. For each one: other names a dataset may use for it, and
# words that make a column a false match (a "dislikes" column is not "likes").
EXPECTED_FIELDS = {
    "description": {"names": ["description", "desc", "summary", "details"], "ignore": []},
    "tags": {"names": ["tags", "tag", "keywords", "keyword"], "ignore": ["hashtag"]},
    "hashtags": {"names": ["hashtags", "hashtag"], "ignore": []},
    "category": {"names": ["category", "categories", "genre"], "ignore": []},
    "views": {"names": ["views", "view", "viewcount"], "ignore": []},
    "likes": {"names": ["likes", "like", "likecount"], "ignore": ["dislike"]},
    "comments": {"names": ["comments", "comment", "commentcount"], "ignore": []},
}


# ---------- Small helpers ----------

def print_section(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def percent(part, whole):
    return 0.0 if whole == 0 else part / whole * 100


def shorten(value):
    """One-line version of a value for display, with a note when text was cut."""
    if pd.isna(value):
        return "<missing>"
    text = str(value).replace("\r", "").replace("\n", " \\n ")
    if len(text) <= MAX_CHARACTERS_PER_VALUE:
        return text
    hidden = len(text) - MAX_CHARACTERS_PER_VALUE
    return f"{text[:MAX_CHARACTERS_PER_VALUE]}... [{hidden} more characters not shown]"


def split_into_words(column_name):
    """'videoTags', 'video_tags' and 'Video Tags' all become ['video', 'tags']."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(column_name))
    return re.findall(r"[a-z0-9]+", spaced.lower())


def is_text_column(series):
    return pd.api.types.is_string_dtype(series)


def is_number_column(series):
    # Yes/no columns count as numbers in pandas, so they are excluded here.
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)


def rows_with_text(series):
    """True where the cell has real text. Blank or space-only cells count as empty."""
    return series.notna() & series.astype(str).str.strip().ne("")


# ---------- Finding and loading the file ----------

def choose_csv_file(path_from_user):
    """Return the CSV to inspect, or None after explaining what to do."""
    if path_from_user is not None:
        return path_from_user

    if not RAW_DATA_FOLDER.is_dir():
        print(f"Error: folder not found: {RAW_DATA_FOLDER}", file=sys.stderr)
        return None

    csv_files = sorted(RAW_DATA_FOLDER.glob("*.csv"))
    if len(csv_files) == 1:
        return csv_files[0]

    if len(csv_files) > 1:
        print(f"{len(csv_files)} CSV files are in {RAW_DATA_FOLDER}.")
        print("Run the script again with the one you want to inspect:")
        for csv_file in csv_files:
            print(f"  {csv_file.name}")
        return None

    print(f"Error: no CSV file found in {RAW_DATA_FOLDER}", file=sys.stderr)
    other_files = sorted(item.name for item in RAW_DATA_FOLDER.iterdir())
    if other_files:
        print("These files are there instead:", file=sys.stderr)
        for name in other_files:
            print(f"  {name}", file=sys.stderr)
        print("A zip file must be extracted first. A .part file is an unfinished download.", file=sys.stderr)
    return None


def why_not_a_csv(csv_path):
    """A plain-words reason when the file is obviously not a CSV, otherwise None."""
    if csv_path.suffix.lower() == ".part":
        return "this is an unfinished download (.part). Finish the download first."
    with open(csv_path, "rb") as file:
        first_bytes = file.read(4)
    if first_bytes == b"PK\x03\x04":
        return "this is a zip archive, not a CSV. Extract it first."
    return None


def load_dataset(csv_path, encoding):
    """Read the CSV into a DataFrame. On a problem, print why and return None."""
    if not csv_path.exists():
        print(f"Error: file not found: {csv_path}", file=sys.stderr)
        return None
    if not csv_path.is_file():
        print(f"Error: not a file: {csv_path}", file=sys.stderr)
        return None

    try:
        reason = why_not_a_csv(csv_path)
        if reason is None:
            # low_memory=False reads the whole file at once, so each column gets one type.
            return pd.read_csv(csv_path, encoding=encoding, low_memory=False)
        message = reason
    except pd.errors.EmptyDataError:
        message = "the file is empty or has no header row."
    except pd.errors.ParserError as error:
        message = f"the file is not a valid CSV ({error})."
    except UnicodeDecodeError:
        message = f"could not read the file as {encoding}. Try: --encoding latin-1"
    except LookupError:
        message = f"unknown encoding '{encoding}'."
    except OSError as error:
        message = f"the file could not be opened ({error})."
    except ValueError as error:
        message = f"the file could not be read as a CSV ({error})."

    print(f"Error: {message}", file=sys.stderr)
    return None


# ---------- Matching our terms to the dataset's column names ----------

def find_possible_columns(dataframe, expected_name):
    """Columns that might hold the field we expect. Nothing is renamed."""
    rules = EXPECTED_FIELDS[expected_name]
    matches = []
    for column in dataframe.columns:
        words = split_into_words(column)
        joined = "".join(words)
        name_fits = joined in rules["names"] or any(word in rules["names"] for word in words)
        is_false_match = any(skip in joined for skip in rules["ignore"])
        if name_fits and not is_false_match:
            matches.append(column)
    return matches


def describe_columns(dataframe, column_names):
    return ", ".join(f"{name} ({dataframe[name].dtype})" for name in column_names)


def note_columns_that_are_not(kind, dataframe, candidates, usable):
    for name in candidates:
        if name not in usable:
            print(f"  Skipped '{name}': it holds {dataframe[name].dtype} values, not {kind}.")


# ---------- Sections 1 to 6: what is in the file ----------

def show_dimensions(dataframe):
    print_section("1. Dimensions")
    print(f"Rows:    {len(dataframe):,}")
    print(f"Columns: {len(dataframe.columns):,}")


def warn_if_pandas_renamed_columns(csv_path, encoding, dataframe):
    """Pandas renames duplicate or blank headers while loading (a, a.1, Unnamed: 0)."""
    with open(csv_path, newline="", encoding=encoding) as file:
        header_in_file = next(csv.reader(file), [])
    if header_in_file:
        header_in_file[0] = header_in_file[0].lstrip("﻿")  # byte order mark

    loaded_names = list(dataframe.columns)
    if len(header_in_file) != len(loaded_names):
        return
    changed = [(old, new) for old, new in zip(header_in_file, loaded_names) if old != new]
    if changed:
        print("\nWARNING: pandas changed these column names while loading:")
        for old_name, new_name in changed:
            print(f"  '{old_name}' in the file became '{new_name}'")


def show_columns_and_types(dataframe, csv_path, encoding):
    print_section("2. Column names and data types")
    for position, name in enumerate(dataframe.columns, start=1):
        print(f"{position:>3}. {name}   ({dataframe[name].dtype})")
    warn_if_pandas_renamed_columns(csv_path, encoding, dataframe)


def show_first_records(dataframe):
    print_section(f"3. First {RECORDS_TO_PREVIEW} records")
    records = dataframe.head(RECORDS_TO_PREVIEW).to_dict(orient="records")
    if not records:
        print("The file has a header but no rows.")
        return
    for record_number, record in enumerate(records, start=1):
        print(f"--- Record {record_number} ---")
        for column_name, value in record.items():
            print(f"{column_name}: {shorten(value)}")
        print()


def show_missing_values(dataframe):
    print_section("4. Missing values per column")
    missing_counts = dataframe.isna().sum()
    table = pd.DataFrame(
        {
            "missing": missing_counts,
            "percent": [round(percent(count, len(dataframe)), 1) for count in missing_counts],
        }
    )
    print(table.to_string())
    columns_with_gaps = int((missing_counts > 0).sum())
    print(f"\n{columns_with_gaps} of {len(dataframe.columns)} columns have at least one missing value.")


def show_duplicate_rows(dataframe):
    print_section("5. Duplicate rows")
    # duplicated() marks every repeat of an earlier row, so the first copy is not counted.
    duplicate_count = int(dataframe.duplicated().sum())
    print(f"Rows that exactly repeat an earlier row: {duplicate_count:,} "
          f"({percent(duplicate_count, len(dataframe)):.2f}% of {len(dataframe):,})")


def show_category_distribution(dataframe, category_columns):
    print_section("6. Category distribution")
    if not category_columns:
        print("No category column found. See section 7 for other possible names.")
        return
    if dataframe.empty:
        print("A category column exists, but the file has no rows to count.")
        return

    for column_name in category_columns:
        counts = dataframe[column_name].value_counts(dropna=False)
        print(f"Column: {column_name}  ({dataframe[column_name].nunique()} distinct values)")
        table = pd.DataFrame(
            {
                "rows": counts,
                "percent": [round(percent(count, len(dataframe)), 1) for count in counts],
            }
        )
        print(table.head(MAX_CATEGORY_ROWS_SHOWN).to_string())
        if len(table) > MAX_CATEGORY_ROWS_SHOWN:
            print(f"... and {len(table) - MAX_CATEGORY_ROWS_SHOWN} more values not shown")
        print()


# ---------- Section 7: our terms against the dataset's names ----------

def show_expected_fields(dataframe, possible_columns):
    print_section("7. Our terms against the dataset's column names")
    print("Possible matches are found by name only. No column is renamed.\n")
    print(f"{'Our term':<13}{'Exact name?':<13}Possible matching columns")
    print(f"{'-' * 12} {'-' * 12} {'-' * 40}")
    for field, columns in possible_columns.items():
        has_exact_name = any(str(column).lower() == field for column in dataframe.columns)
        matches = describe_columns(dataframe, columns) if columns else "none found"
        print(f"{field:<13}{'yes' if has_exact_name else 'no':<13}{matches}")


# ---------- Section 8: what the dataset really contains ----------
# Each check prints its details and returns a one-line answer for the summary.

def check_descriptions(dataframe, candidates):
    print("\n[Full video descriptions]")
    text_columns = [name for name in candidates if is_text_column(dataframe[name])]
    note_columns_that_are_not("text", dataframe, candidates, text_columns)
    if not text_columns:
        return "no description column found"

    column_name = text_columns[0]
    descriptions = dataframe.loc[rows_with_text(dataframe[column_name]), column_name].astype(str)
    print(f"  Column: {column_name}")
    print(f"  Rows with a description: {len(descriptions):,} of {len(dataframe):,} "
          f"({percent(len(descriptions), len(dataframe)):.1f}%)")
    if descriptions.empty:
        return f"column '{column_name}' exists but is empty"

    lengths = descriptions.str.len()
    print(f"  Length in characters: shortest {lengths.min():,}, median {int(lengths.median()):,}, "
          f"average {int(lengths.mean()):,}, longest {lengths.max():,}")
    ellipsis_share = descriptions.str.contains(ENDS_WITH_ELLIPSIS_PATTERN).mean()
    print(f"  Descriptions ending in '...': {ellipsis_share:.1%}")

    reasons = []
    if lengths.max() <= SNIPPET_MAX_CHARACTERS:
        reasons.append(f"none is longer than {SNIPPET_MAX_CHARACTERS} characters")
    if ellipsis_share >= ELLIPSIS_SHARE_THAT_SUGGESTS_TRUNCATION:
        reasons.append(f"{ellipsis_share:.0%} end in '...'")

    if reasons:
        print(f"  Result: possibly truncated ({'; '.join(reasons)}).")
        return f"column '{column_name}', but possibly truncated"
    print("  Result: no sign of truncation. Still, read a few records to be sure.")
    return f"yes, in '{column_name}' ({percent(len(descriptions), len(dataframe)):.0f}% of rows), looks full"


def check_tags(dataframe, candidates):
    print("\n[Actual YouTube tags]")
    text_columns = [name for name in candidates if is_text_column(dataframe[name])]
    for name in candidates:
        if name not in text_columns:
            hint = " It looks like a tag count, not the tags themselves." if is_number_column(dataframe[name]) else ""
            print(f"  Skipped '{name}': it holds {dataframe[name].dtype} values, not text.{hint}")
    if not text_columns:
        return "no, only a count or nothing" if candidates else "no tags column found"

    column_name = text_columns[0]
    texts = dataframe.loc[rows_with_text(dataframe[column_name]), column_name].astype(str)
    is_placeholder = texts.str.strip().str.lower().isin(PLACEHOLDER_TAG_VALUES)
    real_tags = texts[~is_placeholder]
    print(f"  Column: {column_name}")
    print(f"  Rows with real tags:     {len(real_tags):,} of {len(dataframe):,} "
          f"({percent(len(real_tags), len(dataframe)):.1f}%)")
    print(f"  Rows with a placeholder: {int(is_placeholder.sum()):,} (such as [none], not real tags)")
    print(f"  Rows with nothing:       {len(dataframe) - len(texts):,}")
    for example in real_tags.head(EXAMPLES_SHOWN):
        print(f"    e.g. {shorten(example)}")

    if real_tags.empty:
        return f"column '{column_name}' exists but holds no real tags"
    if real_tags.str.fullmatch(r"\d+").mean() > 0.9:
        return f"no, '{column_name}' holds numbers (a count), not tags"
    return f"yes, in '{column_name}' ({percent(len(real_tags), len(dataframe)):.0f}% of rows have real tags)"


def check_hashtags(dataframe, hashtag_columns, description_columns):
    print("\n[Hashtags in descriptions]")
    text_hashtag_columns = [name for name in hashtag_columns if is_text_column(dataframe[name])]
    if text_hashtag_columns:
        print(f"  A separate hashtag column exists: {', '.join(map(str, text_hashtag_columns))}")
    else:
        print("  No separate hashtag column. Hashtags can only be inside descriptions.")

    text_columns = [name for name in description_columns if is_text_column(dataframe[name])]
    if not text_columns:
        print("  Not checked inside descriptions: there is no description text column.")
        return "separate column only" if text_hashtag_columns else "no"

    column_name = text_columns[0]
    descriptions = dataframe.loc[rows_with_text(dataframe[column_name]), column_name].astype(str)
    with_hashtag = int(descriptions.str.contains(HASHTAG_PATTERN).sum())
    share = percent(with_hashtag, len(descriptions))
    print(f"  '{column_name}': {with_hashtag:,} of {len(descriptions):,} descriptions "
          f"contain at least one #hashtag ({share:.1f}%)")
    if with_hashtag == 0:
        return "no hashtags found in descriptions"
    return f"yes, in {share:.1f}% of descriptions"


def check_categories(dataframe, candidates, csv_path):
    print("\n[Video categories]")
    if not candidates:
        print("  No category column found.")
        return "no category column found"

    column_name = candidates[0]
    distinct_values = dataframe[column_name].nunique()
    print(f"  Column: {column_name} ({dataframe[column_name].dtype}), {distinct_values} distinct values")
    if distinct_values == 0:
        return f"column '{column_name}' exists but is empty"
    if not is_number_column(dataframe[column_name]):
        return f"yes, names in '{column_name}' ({distinct_values} distinct)"

    print("  The values are numeric IDs, not category names.")
    lookup_files = sorted(path.name for path in csv_path.parent.glob("*.json") if "category" in path.name.lower())
    if lookup_files:
        print(f"  Category names may be in these files next to the CSV: {', '.join(lookup_files)}")
        return f"IDs only in '{column_name}'; names are in separate JSON files"
    return f"IDs only in '{column_name}'; no name lookup file found"


def check_view_like_comment_counts(dataframe, possible_columns):
    print("\n[Views, likes and comments]")
    answers = []
    for field in ["views", "likes", "comments"]:
        candidates = possible_columns[field]
        number_columns = [name for name in candidates if is_number_column(dataframe[name])]
        print(f"  {field}:")
        if not number_columns:
            print("    no numeric column found")
        for name in number_columns:
            values = dataframe[name]
            print(f"    {name}: min {values.min():,.0f}, median {values.median():,.0f}, "
                  f"max {values.max():,.0f}, missing {int(values.isna().sum()):,}")
        for name in candidates:
            if name not in number_columns:
                print(f"    skipped '{name}': it holds {dataframe[name].dtype} values, not counts")
        answers.append(f"{field} = {number_columns[0]}" if number_columns else f"{field} = not found")
    return ", ".join(answers)


def show_content_checks(dataframe, possible_columns, csv_path):
    print_section("8. What the dataset contains")
    print("Blank or space-only cells count as empty.")
    answers = {
        "Full video descriptions": check_descriptions(dataframe, possible_columns["description"]),
        "Actual YouTube tags": check_tags(dataframe, possible_columns["tags"]),
        "Hashtags in descriptions": check_hashtags(dataframe, possible_columns["hashtags"], possible_columns["description"]),
        "Video categories": check_categories(dataframe, possible_columns["category"], csv_path),
        "Views, likes, comments": check_view_like_comment_counts(dataframe, possible_columns),
    }

    print_section("Summary")
    for label, answer in answers.items():
        print(f"{label:<26}{answer}")


# ---------- Running it ----------

def parse_arguments():
    parser = argparse.ArgumentParser(description="Inspect the YouTube metadata CSV without changing it.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        help="path to the CSV file (default: the only CSV in datasets/raw/)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="file encoding (default: utf-8); try latin-1 if loading fails",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()

    # YouTube text is full of emoji that a Windows console cannot always print.
    # Show a "?" for those instead of crashing.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    csv_path = choose_csv_file(arguments.csv_path)
    if csv_path is None:
        return 1
    dataframe = load_dataset(csv_path, arguments.encoding)
    if dataframe is None:
        return 1

    possible_columns = {field: find_possible_columns(dataframe, field) for field in EXPECTED_FIELDS}

    print(f"Inspecting: {csv_path.resolve()}")
    show_dimensions(dataframe)
    show_columns_and_types(dataframe, csv_path, arguments.encoding)
    show_first_records(dataframe)
    show_missing_values(dataframe)
    show_duplicate_rows(dataframe)
    show_category_distribution(dataframe, possible_columns["category"])
    show_expected_fields(dataframe, possible_columns)
    show_content_checks(dataframe, possible_columns, csv_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
