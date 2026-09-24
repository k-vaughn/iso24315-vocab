#!/usr/bin/env python3
"""Generate MkDocs term pages and navigation from modular ITS vocabulary TTL files."""

import logging
import os
import sys
import traceback
from collections import defaultdict
from pathlib import Path

from diagram_generator import generate_diagram
from markdown_generator import (
    generate_collection_pages,
    generate_index,
    generate_markdown,
    generate_prop_list,
    update_mkdocs_nav,
)
from ontology_processor_ttl import MASTER_FILE, process_vocabulary
from utils import (
    get_id,
    get_label,
    get_qname,
    get_repository_url,
    is_abstract,
    is_publishable_term,
    remove_placeholder_term_pages,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
)
log = logging.getLogger("ttl2mkdocs")

_SUMMARY_LINE = "=" * 72


class _SummaryLogHandler(logging.Handler):
    """Collect warning and error log records for a summary at end of run."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.warnings: list[str] = []
        self.log_errors: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            message = record.getMessage()
        if record.levelno >= logging.ERROR:
            self.log_errors.append(message)
        else:
            self.warnings.append(message)


def _attach_summary_handler() -> _SummaryLogHandler:
    handler = _SummaryLogHandler()
    handler.setFormatter(
        logging.Formatter("%(levelname)s - %(filename)s:%(lineno)d - %(message)s")
    )
    logging.getLogger().addHandler(handler)
    return handler


def _print_run_summary(
    errors: list[str],
    warnings: list[str],
    logged_errors: list[str],
) -> int:
    """Reprint warnings and errors after processing. Returns exit code."""
    merged_errors: list[str] = []
    seen: set[str] = set()
    for msg in errors + logged_errors:
        if msg not in seen:
            seen.add(msg)
            merged_errors.append(msg)

    if not warnings and not merged_errors:
        return 0

    print(f"\n{_SUMMARY_LINE}", file=sys.stderr)
    print("RUN SUMMARY", file=sys.stderr)
    print(_SUMMARY_LINE, file=sys.stderr)

    if warnings:
        print(f"\nWarnings ({len(warnings)}):", file=sys.stderr)
        print("-" * 72, file=sys.stderr)
        for index, msg in enumerate(warnings, start=1):
            print(f"  {index}. {msg}", file=sys.stderr)

    if merged_errors:
        print(f"\nErrors ({len(merged_errors)}):", file=sys.stderr)
        print("-" * 72, file=sys.stderr)
        for index, msg in enumerate(merged_errors, start=1):
            print(f"  {index}. {msg}", file=sys.stderr)
            if "\n" in msg:
                for line in msg.splitlines()[1:]:
                    print(f"      {line}", file=sys.stderr)

    print(f"\n{_SUMMARY_LINE}\n", file=sys.stderr)
    return 1 if merged_errors else 0


def main() -> None:
    summary_handler = _attach_summary_handler()
    log.info("Starting ttl2mkdocs.py")
    if len(sys.argv) != 1:
        print("Usage: python ttl2mkdocs.py")
        sys.exit(1)

    root_dir = os.getcwd()
    mkdocs_path = os.path.join(root_dir, "mkdocs.yml")
    if not os.path.exists(mkdocs_path):
        print("Error: mkdocs.yml not found in current directory")
        sys.exit(1)

    docs_dir = os.path.join(root_dir, "docs")
    if not os.path.isdir(docs_dir):
        print("Error: docs directory not found")
        sys.exit(1)

    terms_dir = os.path.join(docs_dir, "terms")
    os.makedirs(terms_dir, exist_ok=True)

    vocab_path = os.path.abspath(os.path.join(docs_dir, MASTER_FILE))
    if not os.path.isfile(vocab_path):
        log.error("Error: %s not found in docs/", MASTER_FILE)
        sys.exit(1)

    global_patterns: dict = {}
    global_all_classes: set[str] = set()
    global_term_labels: set[str] = set()
    global_all_class_uris: set[str] = set()
    abstract_map: dict[str, bool] = {}
    ontology_info: dict = {}
    errors: list[str] = []
    processed_count = 0
    ns_to_ontology: dict[str, str] = {}
    class_to_onts: dict[str, list[str]] = defaultdict(list)
    g = None
    ns = None
    local_classes: list = []
    modules: dict = {}
    term_collection_map: dict = {}
    repo_url = get_repository_url(mkdocs_path)

    ontology_name = os.path.splitext(os.path.basename(vocab_path))[0]
    log.info("Processing vocabulary: %s", vocab_path)

    try:
        result = process_vocabulary(Path(docs_dir), errors, ontology_info)
        if result[0] is None:
            log.error("Error: vocabulary processing failed")
            sys.exit(1)

        (
            g,
            ns,
            prefix_map,
            classes,
            local_classes,
            prop_map,
            global_patterns,
            modules,
            term_collection_map,
        ) = result
        ns_to_ontology[ns] = ontology_name

        generate_collection_pages(docs_dir, g, modules, global_patterns, errors, repo_url)

        for cls in classes:
            cls_qname = get_qname(g, cls, ns, prefix_map)
            abstract_map[cls_qname] = is_abstract(cls, g, ns)
            if cls_qname != "ITSThing":
                global_all_classes.add(cls_qname)
            if is_publishable_term(cls, g):
                label = get_label(g, cls)
                global_term_labels.add(label)
                global_all_class_uris.add(str(cls))
                class_to_onts[label].append(ontology_name)

        prop_list = generate_prop_list(g, global_all_class_uris, ns, prefix_map)

        for cls in sorted(local_classes, key=lambda uri: get_label(g, uri).lower()):
            if not is_publishable_term(cls, g):
                continue
            cls_name = get_label(g, cls)
            cls_id = get_id(cls_name)
            log.debug("Processing class: %s", cls_name)
            try:
                generate_diagram(
                    g,
                    cls,
                    cls_name,
                    cls_id,
                    ns,
                    global_all_classes,
                    abstract_map,
                    vocab_path,
                    errors,
                    prefix_map,
                    ontology_name,
                    ns_to_ontology,
                )
                generate_markdown(
                    g,
                    cls,
                    cls_name,
                    global_patterns,
                    global_all_classes,
                    global_term_labels,
                    ns,
                    vocab_path,
                    errors,
                    prefix_map,
                    prop_list,
                    ns_to_ontology,
                    class_to_onts,
                    term_collection_map,
                    repo_url,
                )
                processed_count += 1
            except Exception as exc:
                error_msg = (
                    f"Error processing class {cls_name}: {exc}\n{traceback.format_exc()}"
                )
                errors.append(error_msg)
                log.error(error_msg)
    except Exception as exc:
        error_msg = f"Error processing vocabulary: {exc}\n{traceback.format_exc()}"
        errors.append(error_msg)
        log.error(error_msg)

    try:
        log.info("Total patterns for nav: %d", len(global_patterns))
        if g is not None and ns is not None:
            update_mkdocs_nav(
                mkdocs_path,
                global_patterns,
                errors,
                class_to_onts,
                ontology_info,
                vocab_path,
                local_classes,
                g,
                ns,
                modules,
            )
    except Exception as exc:
        error_msg = f"Error updating mkdocs.yml: {exc}\n{traceback.format_exc()}"
        errors.append(error_msg)
        log.error(error_msg)

    try:
        generate_index(
            docs_dir,
            vocab_path,
            ontology_info,
            global_patterns,
            errors,
            class_to_onts,
            repo_url,
        )
    except Exception as exc:
        error_msg = f"Error generating index.md: {exc}\n{traceback.format_exc()}"
        errors.append(error_msg)
        log.error(error_msg)

    removed = remove_placeholder_term_pages(terms_dir)
    if removed:
        log.info("Removed %d placeholder term pages", removed)

    log.info("Total processed classes: %d", processed_count)
    exit_code = _print_run_summary(
        errors,
        summary_handler.warnings,
        summary_handler.log_errors,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
