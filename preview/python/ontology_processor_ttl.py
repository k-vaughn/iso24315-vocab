# ontology_processor_ttl.py
"""Load modular ITS vocabulary Turtle files and build collection metadata for MkDocs."""

from __future__ import annotations

import logging
import os
import re
import textwrap
import traceback
from pathlib import Path
from urllib.parse import urljoin

from rdflib import Graph, Literal, OWL, RDF, RDFS, URIRef
from rdflib.namespace import DC, DCTERMS, SKOS

from utils import (
    concept_registry_path,
    get_label,
    get_ontology_metadata,
    get_qname,
    insert_spaces,
    is_publishable_term,
    md_table_delimiter,
    update_concept_registry,
    get_repository_url,
)

log = logging.getLogger("ttl2mkdocs")

BASE = "https://w3id.org/itsdata/metr/"
MASTER_FILE = "metrVocabulary.ttl"
IMPORT_REF = re.compile(r"<\s*([^>]+)\s*>")
ONTOLOGY_NAME = re.compile(r":([\w-]+)\s+a\s+owl:Ontology")
ONTOLOGY_TITLE = re.compile(r'dcterms:title\s+"([^"]+)"@en')


def parse_ontology_description(path: Path) -> str | None:
    match = re.search(r'dcterms:description\s+"([^"]+)"@en', path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def parse_imports(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    start = text.find("owl:imports")
    if start == -1:
        return []
    remainder = text[start:]
    end = len(remainder)
    for match in re.finditer(r"\.\s*(?:\n|$)", remainder):
        end = match.start()
        break
    return IMPORT_REF.findall(remainder[:end])


def parse_ontology_local_name(path: Path) -> str | None:
    match = ONTOLOGY_NAME.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def parse_ontology_title(path: Path) -> str | None:
    match = ONTOLOGY_TITLE.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def classify_module(filename: str) -> str:
    if filename == MASTER_FILE:
        return "master"
    if filename == "terms-group.ttl":
        return "terms"
    if filename == "core.ttl":
        return "core"
    if filename.endswith("-group.ttl"):
        return "group"
    if filename.endswith("-pattern.ttl"):
        return "pattern"
    return "other"


def import_module_name(import_path: str) -> str | None:
    match = re.match(r"(.+)-(group|pattern)\.ttl$", import_path)
    return match.group(1) if match else None


def collection_title(name: str) -> str:
    title = insert_spaces(name)
    if title.endswith(" Terms"):
        return title[0].upper() + title[1:]
    if title.endswith("Terms"):
        return title[:-5] + " Terms"
    return title[0].upper() + title[1:] if title else title


def collect_import_closure(start: Path, docs_dir: Path) -> list[Path]:
    seen: set[Path] = set()
    queue = [start.resolve()]
    ordered: list[Path] = []
    while queue:
        path = queue.pop(0)
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        ordered.append(path)
        for imp in parse_imports(path):
            if imp.startswith("http"):
                continue
            child = (docs_dir / imp).resolve()
            if child not in seen:
                queue.append(child)
    return ordered


def discover_modules(docs_dir: Path) -> dict[str, dict]:
    master = docs_dir / MASTER_FILE
    if not master.is_file():
        raise FileNotFoundError(f"{MASTER_FILE} not found in {docs_dir}")

    modules: dict[str, dict] = {}
    for path in collect_import_closure(master, docs_dir):
        local_name = parse_ontology_local_name(path)
        if not local_name:
            continue
        modules[local_name] = {
            "path": path,
            "imports": parse_imports(path),
            "title": parse_ontology_title(path),
            "kind": classify_module(path.name),
            "order": 99999,
        }

    def assign_order(local_name: str, order: int) -> None:
        if local_name not in modules:
            return
        modules[local_name]["order"] = order
        child_idx = 0
        for imp in modules[local_name]["imports"]:
            child = import_module_name(imp)
            if child and child in modules:
                assign_order(child, child_idx)
                child_idx += 1

    if "terms" in modules:
        assign_order("terms", 0)

    return modules


def clause_sort_key(clause) -> tuple:
    if clause is None:
        return (99999,)
    try:
        return tuple(int(part) for part in str(clause).split("."))
    except ValueError:
        return (99999,)


def clause_literal_display(clause) -> str:
    if clause is None:
        return ""
    if isinstance(clause, Literal):
        return str(clause.value).strip() if clause.value is not None else ""
    return str(clause).strip()


def clause_keys_from_class_entries(classes: list) -> list[tuple]:
    """Extract clause sort keys from class entry tuples."""
    keys: list[tuple] = []
    for entry in classes:
        if len(entry) >= 5:
            key = entry[4]
        elif len(entry) >= 4:
            key = entry[3]
        else:
            continue
        if key != (99999,):
            keys.append(key)
    return keys


def clause_tuple_to_display(key: tuple) -> str:
    if not key or key == (99999,):
        return ""
    return ".".join(str(part) for part in key)


def parent_clause_from_keys(keys: list[tuple]) -> tuple[tuple, str]:
    """Return the parent clause shared by member clause keys (sort_key, display)."""
    if not keys:
        return (99999,), ""
    roots = [k[:-1] for k in keys if len(k) >= 2]
    if roots and all(r == roots[0] for r in roots):
        parent = roots[0]
    else:
        parent_parts: list[int] = []
        for parts in zip(*keys):
            if len(set(parts)) == 1:
                parent_parts.append(parts[0])
            else:
                break
        parent = tuple(parent_parts)
    return parent, clause_tuple_to_display(parent)


def parent_clause_from_class_entries(classes: list) -> tuple[tuple, str]:
    """Return the parent clause for a pattern or group member list."""
    return parent_clause_from_keys(clause_keys_from_class_entries(classes))


def validate_member_clause_keys(
    collection_name: str,
    member_keys: list[tuple],
    member_labels: list[str] | None = None,
) -> None:
    """Warn when members lack a common root clause or use non-sequential numbering."""
    if not member_keys:
        return
    labels = member_labels or [str(k) for k in member_keys]
    by_root: dict[tuple, list[tuple[int, str]]] = {}
    for key, label in zip(member_keys, labels):
        root = key[:-1] if len(key) >= 2 else key
        by_root.setdefault(root, []).append((key[-1], label))

    if len(by_root) > 1:
        roots_display = ", ".join(clause_tuple_to_display(r) for r in sorted(by_root))
        log.warning(
            "%s: members do not share the same root clause (found roots: %s)",
            collection_name,
            roots_display,
        )

    for root, numbered in by_root.items():
        suffixes = [n for n, _ in numbered]
        if len(suffixes) != len(set(suffixes)):
            seen: dict[int, list[str]] = {}
            for suffix, label in numbered:
                seen.setdefault(suffix, []).append(label)
            overlaps = ", ".join(
                f"{clause_tuple_to_display(root)}.{suffix} ({', '.join(names)})"
                for suffix, names in sorted(seen.items())
                if len(names) > 1
            )
            log.warning(
                "%s: overlapping clause numbers under %s: %s",
                collection_name,
                clause_tuple_to_display(root),
                overlaps,
            )
            suffixes = sorted(set(suffixes))

        unique = sorted(set(suffixes))
        expected = list(range(unique[0], unique[-1] + 1))
        if unique != expected:
            missing = sorted(set(expected) - set(unique))
            log.warning(
                "%s: non-sequential clause numbers under %s (missing: %s)",
                collection_name,
                clause_tuple_to_display(root),
                ", ".join(f"{clause_tuple_to_display(root)}.{n}" for n in missing),
            )


def validate_collection_clauses(
    modules: dict[str, dict],
    global_patterns: dict[str, dict],
) -> None:
    """Validate clause numbering for every pattern and group in the vocabulary."""
    for local_name, mod in modules.items():
        kind = mod["kind"]
        if kind not in {"group", "pattern"}:
            continue
        title = mod.get("title") or collection_title(local_name)
        coll_uri = BASE + local_name
        gp = global_patterns.get(coll_uri)
        if not gp:
            continue
        if kind == "pattern":
            classes = gp.get("classes", [])
            keys = clause_keys_from_class_entries(classes)
            labels = [entry[1] for entry in classes if len(entry) >= 2]
            validate_member_clause_keys(title, keys, labels)
        else:
            keys: list[tuple] = []
            labels: list[str] = []
            for sub_coll in gp.get("subcollections", []):
                sub_local = sub_coll.removeprefix(BASE)
                sub_gp = global_patterns.get(sub_coll, {})
                sub_mod = modules.get(sub_local, {})
                if not sub_mod or sub_mod["kind"] != "pattern":
                    continue
                sub_title = sub_mod.get("title") or collection_title(sub_local)
                key, _ = parent_clause_from_class_entries(sub_gp.get("classes", []))
                if key == (99999,):
                    continue
                keys.append(key)
                labels.append(sub_title)
            validate_member_clause_keys(title, keys, labels)


def collection_clause_sort_key(gp: dict, global_patterns: dict) -> tuple:
    """Clause sort key for a pattern (parent clause) or group (min parent clause of patterns)."""
    if gp.get("classes"):
        return parent_clause_from_class_entries(gp["classes"])[0]
    keys = []
    for sub_coll in gp.get("subcollections", []):
        sub_gp = global_patterns.get(sub_coll)
        if sub_gp and sub_gp.get("classes"):
            key = parent_clause_from_class_entries(sub_gp["classes"])[0]
            if key != (99999,):
                keys.append(key)
    return min(keys) if keys else (99999,)


def collect_pattern_classes(
    pattern_path: Path,
    graph: Graph,
    ns: str,
    ontology_name: str,
) -> list[tuple[str, str, str, str, tuple]]:
    local = Graph()
    local.parse(pattern_path, format="turtle")
    clause_prop = URIRef(ns + "clause")
    classes: list[tuple[str, str, str, str, tuple]] = []
    for cls in local.subjects(RDF.type, OWL.Class):
        if cls == OWL.Thing:
            continue
        if not is_publishable_term(cls, graph) and not is_publishable_term(cls, local):
            continue
        label = get_label(graph, cls) or get_label(local, cls)
        if not label or not label.strip():
            continue
        clause = graph.value(cls, clause_prop) or local.value(cls, clause_prop)
        classes.append(
            (
                str(cls),
                label,
                ontology_name,
                clause_literal_display(clause),
                clause_sort_key(clause),
            )
        )
    classes.sort(key=lambda item: (item[4], item[1].lower()))
    return classes


def build_global_patterns(
    modules: dict[str, dict],
    pattern_classes: dict[str, list],
) -> dict[str, dict]:
    global_patterns: dict[str, dict] = {}
    for local_name, mod in modules.items():
        if mod["kind"] not in {"terms", "group", "pattern"}:
            continue
        coll_uri = BASE + local_name
        gp = {
            "name": mod.get("title") or collection_title(local_name),
            "order": mod.get("order", 99999),
            "subcollections": [],
            "classes": pattern_classes.get(local_name, []),
        }
        for imp in mod["imports"]:
            child = import_module_name(imp)
            if child and child in modules and modules[child]["kind"] in {"group", "pattern"}:
                gp["subcollections"].append(BASE + child)
        global_patterns[coll_uri] = gp
    return global_patterns


def build_term_collection_map(
    modules: dict[str, dict],
    pattern_classes: dict[str, list],
) -> dict[str, dict]:
    """Map term prefLabel to parent group/pattern display titles."""
    parent: dict[str, str] = {}
    for local_name, mod in modules.items():
        for imp in mod["imports"]:
            child = import_module_name(imp)
            if child and child in modules:
                parent[child] = local_name

    pattern_to_group: dict[str, str] = {}
    for local_name, mod in modules.items():
        if mod["kind"] != "pattern":
            continue
        ancestor = parent.get(local_name)
        while ancestor:
            if modules[ancestor]["kind"] == "group":
                pattern_to_group[local_name] = ancestor
                break
            ancestor = parent.get(ancestor)

    def module_title(local_name: str) -> str:
        mod = modules[local_name]
        return mod.get("title") or collection_title(local_name)

    term_map: dict[str, dict] = {}
    for pattern_local, classes in pattern_classes.items():
        pattern_title = module_title(pattern_local)
        group_local = pattern_to_group.get(pattern_local)
        group_title = module_title(group_local) if group_local else None
        for _, label, _, _, _ in classes:
            term_map[label] = {
                "group_title": group_title,
                "pattern_title": pattern_title,
            }
    return term_map


def parse_concept_registry(script_dir: str) -> dict:
    root_dir = os.getcwd()
    docs_dir = os.path.join(root_dir, "docs")
    registry_path = concept_registry_path(docs_dir)
    legacy_path = os.path.join(docs_dir, "concept_registry.md")
    if not os.path.exists(registry_path) and os.path.exists(legacy_path):
        registry_path = legacy_path
    if not os.path.exists(registry_path):
        os.makedirs(os.path.dirname(registry_path), exist_ok=True)
        with open(registry_path, "w", encoding="utf-8") as f:
            f.write("| name | description |\n")
            f.write(md_table_delimiter(2))
        log.info("Created new concept registry at %s", registry_path)
        return {}

    registry: dict = {}
    content = open(registry_path, encoding="utf-8").read()
    in_table = False
    headers = None
    for line in content.splitlines():
        if line.strip().startswith("|"):
            if not in_table:
                headers = [h.strip().lower() for h in line.split("|") if h.strip()]
                in_table = True
            elif headers and not line.strip().startswith("|---"):
                values = [v.strip() for v in line.split("|") if v.strip()]
                if len(values) < 1:
                    continue
                try:
                    if "uri" in headers:
                        uri = values[headers.index("uri")]
                        name_cell = values[headers.index("name")]
                    else:
                        uri = None
                        name_cell = values[headers.index("name")]
                    name_match = re.search(r"\[(.*?)\]", name_cell)
                    if not name_match:
                        continue
                    name = name_match.group(1)
                    description = (
                        values[headers.index("description")]
                        if "description" in headers and len(values) > headers.index("description")
                        else ""
                    )
                    if uri:
                        registry[uri] = {"name": name, "type": "class", "description": description}
                except ValueError:
                    continue
    return registry


def load_vocabulary_graph(module_paths: list[Path]) -> Graph:
    graph = Graph()
    graph.bind("", URIRef(BASE))
    for path in module_paths:
        graph.parse(path, format="turtle")
        log.debug("Loaded %s (%d triples so far)", path.name, len(graph))
    return graph


def build_prefix_map(graph: Graph, ns: str) -> dict[str, str]:
    prefix_map = {str(uri): f"{prefix}:" for prefix, uri in graph.namespaces()}
    if ns not in prefix_map:
        prefix_map[ns] = ":"
    return prefix_map


def process_vocabulary(
    docs_dir: Path | str,
    errors: list,
    ontology_info: dict,
) -> tuple:
    """Load modular TTL vocabulary files and return graph metadata for MkDocs generation."""
    docs_dir = Path(docs_dir)
    master_path = (docs_dir / MASTER_FILE).resolve()
    try:
        modules = discover_modules(docs_dir)
    except FileNotFoundError as exc:
        errors.append(str(exc))
        log.error(str(exc))
        return None, None, None, None, None, None, None, None

    module_paths = [mod["path"] for mod in modules.values()]
    try:
        graph = load_vocabulary_graph(module_paths)
        if len(graph) == 0:
            raise ValueError("RDF graph is empty after loading vocabulary TTL files")
        log.info(
            "Loaded vocabulary from %d TTL modules (%d triples)",
            len(module_paths),
            len(graph),
        )
    except Exception as exc:
        error_msg = f"Failed to load vocabulary TTL files: {exc}\n{traceback.format_exc()}"
        errors.append(error_msg)
        log.error(error_msg)
        return None, None, None, None, None, None, None, None

    ns = BASE
    prefix_map = build_prefix_map(graph, ns)
    ontology_name = master_path.stem

    script_dir = os.path.dirname(os.path.realpath(__file__))
    registry = parse_concept_registry(script_dir)

    for uri, info in registry.items():
        if info["type"] == "object_property":
            graph.add((URIRef(uri), RDF.type, OWL.ObjectProperty))
        elif info["type"] == "datatype_property":
            graph.add((URIRef(uri), RDF.type, OWL.DatatypeProperty))

    new_concepts: dict = {}
    for cls in graph.subjects(RDF.type, OWL.Class):
        if not is_publishable_term(cls, graph):
            continue
        uri = str(cls)
        if uri not in registry and uri not in new_concepts:
            description = (
                graph.value(cls, SKOS.definition)
                or graph.value(cls, DCTERMS.description)
                or graph.value(cls, DC.description)
                or graph.value(cls, RDFS.comment)
                or "-"
            )
            new_concepts[uri] = {
                "name": get_label(graph, cls),
                "type": "class",
                "description": str(description) if isinstance(description, Literal) else description,
            }

    for prop_type in (OWL.ObjectProperty, OWL.DatatypeProperty):
        for prop in graph.subjects(RDF.type, prop_type):
            uri = str(prop)
            if uri not in registry and uri not in new_concepts:
                description = (
                    graph.value(prop, SKOS.definition)
                    or graph.value(prop, DCTERMS.description)
                    or graph.value(prop, DC.description)
                    or graph.value(prop, RDFS.comment)
                    or "-"
                )
                new_concepts[uri] = {
                    "name": get_label(graph, prop),
                    "type": "object_property" if prop_type == OWL.ObjectProperty else "datatype_property",
                    "description": str(description) if isinstance(description, Literal) else description,
                }

    for uri, info in new_concepts.items():
        if uri not in registry:
            registry[uri] = info

    dc_title = parse_ontology_title(master_path) or get_ontology_metadata(graph, ns, DCTERMS.title) or "Untitled Ontology"
    dc_description = (
        parse_ontology_description(master_path)
        or get_ontology_metadata(graph, ns, DCTERMS.description)
        or get_ontology_metadata(graph, ns, DC.description)
        or get_ontology_metadata(graph, ns, RDFS.comment)
        or "-"
    )
    if dc_description != "-":
        dc_description = textwrap.dedent(dc_description).strip()

    ontology_info[str(master_path)] = {
        "title": dc_title,
        "description": dc_description,
        "patterns": set(),
        "non_pattern_classes": set(),
        "ontology_name": ontology_name,
    }

    pattern_classes: dict[str, list] = {}
    patterned_labels: set[str] = set()
    for local_name, mod in modules.items():
        if mod["kind"] != "pattern":
            continue
        classes = collect_pattern_classes(mod["path"], graph, ns, ontology_name)
        pattern_classes[local_name] = classes
        ontology_info[str(master_path)]["patterns"].add(
            mod.get("title") or collection_title(local_name)
        )
        for _, label, _, _, _ in classes:
            patterned_labels.add(label)

    global_patterns = build_global_patterns(modules, pattern_classes)
    validate_collection_clauses(modules, global_patterns)
    term_collection_map = build_term_collection_map(modules, pattern_classes)
    update_concept_registry(
        script_dir,
        registry,
        term_collection_map,
        get_repository_url(),
    )

    classes = set(graph.subjects(RDF.type, OWL.Class)) - {OWL.Thing}
    local_classes = [
        cls for cls in classes if urljoin(ns, str(cls)).startswith(ns) and is_publishable_term(cls, graph)
    ]
    log.info("Found %d local classes in namespace %s", len(local_classes), ns)

    non_pattern = {
        get_label(graph, cls)
        for cls in local_classes
        if get_label(graph, cls) not in patterned_labels and get_label(graph, cls) != "ITSThing"
    }
    ontology_info[str(master_path)]["non_pattern_classes"] = non_pattern

    prop_map = {}
    for prop in graph.subjects(RDF.type, OWL.ObjectProperty):
        prop_map[get_qname(graph, prop, ns, prefix_map)] = prop
    for prop in graph.subjects(RDF.type, OWL.DatatypeProperty):
        prop_map[get_qname(graph, prop, ns, prefix_map)] = prop

    return (
        graph,
        ns,
        prefix_map,
        classes,
        local_classes,
        prop_map,
        global_patterns,
        modules,
        term_collection_map,
    )
