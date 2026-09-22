#!/usr/bin/env python3
"""Split itsVocabulary.owl into modular Turtle files by SKOS collection."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD, VANN

from utils import get_filename

CC = Namespace("http://creativecommons.org/ns#")

BASE = "https://w3id.org/itsdata/metr/"
NS = Namespace(BASE)
DEFAULT_LANG = "en"
CLAUSE_PROP = URIRef(BASE + "clause")
CLAUSE_REF_PATTERN = re.compile(r"\((\d+(?:\.\d+)*)\)")

PREFIXES = """\
BASE <https://w3id.org/itsdata/metr/>
PREFIX : <https://w3id.org/itsdata/metr/>
PREFIX cc: <http://creativecommons.org/ns#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX vann: <http://purl.org/vocab/vann/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

MASTER_ONTOLOGY_TRIPLES = {
    DCTERMS.title,
    DCTERMS.description,
    VANN.preferredNamespacePrefix,
    DCTERMS.license,
    CC.attributionName,
    DCTERMS.creator,
    DCTERMS.issued,
    OWL.versionInfo,
    RDFS.comment,
    OWL.versionIRI,
}


def normalize_uri(term: URIRef) -> URIRef:
    text = str(term)
    if "://" in text or ":" in text:
        return term
    return URIRef(BASE + text)


def collapse_literal_whitespace(text: str) -> str:
    """Collapse line breaks and surrounding whitespace to a single line."""
    return " ".join(line.strip() for line in text.splitlines()).strip()


def is_text_literal(literal: Literal) -> bool:
    if literal.datatype:
        dt = str(literal.datatype)
        return dt in {str(XSD.string), "xsd:string"}
    return True


def tag_literal(literal: Literal) -> Literal:
    """Convert plain or xsd:string literals to normalized, language-tagged strings."""
    if not is_text_literal(literal):
        return literal
    text = collapse_literal_whitespace(str(literal))
    lang = literal.language or DEFAULT_LANG
    return Literal(text, lang=lang)


def get_pref_label(graph: Graph, cls: URIRef) -> str | None:
    for _, _, lbl in graph.triples((cls, SKOS.prefLabel, None)):
        if isinstance(lbl, Literal):
            text = collapse_literal_whitespace(str(lbl))
            if text:
                return text
    return None


def build_clause_index(graph: Graph) -> dict[str, tuple[str, str]]:
    """Map clause numbers to (skos:prefLabel, term page filename stem)."""
    index: dict[str, tuple[str, str]] = {}
    for cls in graph.subjects(RDF.type, OWL.Class):
        clause = graph.value(cls, CLAUSE_PROP)
        pref_str = get_pref_label(graph, cls)
        if clause is None or pref_str is None:
            continue
        clause_str = collapse_literal_whitespace(str(clause))
        index[clause_str] = (pref_str, get_filename(pref_str))
    return index


ARTICLES = frozenset({"a", "an", "the"})
PREPOSITIONS = frozenset(
    {
        "of",
        "for",
        "to",
        "from",
        "in",
        "on",
        "at",
        "by",
        "with",
        "using",
        "and",
        "or",
        "when",
        "into",
        "upon",
        "via",
        "per",
        "between",
        "through",
        "during",
        "within",
        "without",
        "toward",
        "towards",
        "over",
        "under",
        "about",
        "against",
        "among",
        "around",
        "before",
        "behind",
        "below",
        "beneath",
        "beside",
        "beyond",
        "despite",
        "except",
        "inside",
        "near",
        "off",
        "outside",
        "since",
        "until",
        "while",
    }
)


POSSESSIVE_SUFFIXES = ("'s", "\u2019s", "'", "\u2019")


def _plural_single_word(word: str) -> list[str]:
    forms: list[str] = []
    if not word:
        return forms
    lower = word.lower()
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        forms.append(word[:-1] + "ies")
    elif lower.endswith(("s", "x", "z")) or lower.endswith("ch") or lower.endswith("sh"):
        forms.append(word + "es")
    else:
        forms.append(word + "s")
    return forms


def plural_forms(label: str) -> list[str]:
    words = label.split()
    if len(words) == 1:
        return _plural_single_word(label)
    prefix = " ".join(words[:-1]) + " "
    return [prefix + plural for plural in _plural_single_word(words[-1])]


def strip_possessive(text: str) -> str:
    for suffix in POSSESSIVE_SUFFIXES:
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def normalize_term_for_compare(text: str) -> str:
    return strip_possessive(text).lower()


def base_form_matches(display: str, pref_label: str) -> bool:
    normalized = normalize_term_for_compare(display)
    if normalized == pref_label.lower():
        return True
    return any(normalized == plural.lower() for plural in plural_forms(pref_label))


def valid_prefix_before_term(prefix: str) -> bool:
    if not prefix:
        return True
    trimmed = prefix.rstrip()
    if not trimmed:
        return True
    if trimmed.endswith(","):
        return True
    last_token = trimmed.rsplit(" ", 1)[-1].lower().strip("<>")
    return last_token in ARTICLES or last_token in PREPOSITIONS


def find_term_display_before_reference(before: str, pref_label: str) -> tuple[str, int] | None:
    """Return the source text span and its start index when it references prefLabel."""
    stripped = before.rstrip()
    if not stripped:
        return None

    word_count = len(pref_label.split())
    tokens = stripped.split(" ")
    max_words = min(len(tokens), word_count + 1)

    for n in range(1, max_words + 1):
        display = " ".join(tokens[-n:])
        if not base_form_matches(display, pref_label):
            continue
        label_start = len(stripped) - len(display)
        prefix = stripped[:label_start]
        if valid_prefix_before_term(prefix):
            return display, label_start

    return None


def linkify_definition(text: str, clause_index: dict[str, tuple[str, str]]) -> str:
    """Replace `prefLabel (clause)` with markdown links when the reference resolves."""
    parts: list[str] = []
    pos = 0
    for match in CLAUSE_REF_PATTERN.finditer(text):
        clause = match.group(1)
        start_paren = match.start()
        entry = clause_index.get(clause)

        if entry is not None:
            pref_label, page_stem = entry
            before = text[:start_paren]
            found = find_term_display_before_reference(before, pref_label)
            if found is not None:
                display, label_start = found
                parts.append(text[pos:label_start])
                parts.append(f"[{display}]({page_stem}.md)")
                pos = match.end()
                continue

        parts.append(text[pos:match.end()])
        pos = match.end()

    parts.append(text[pos:])
    return "".join(parts)


def linkify_definitions(graph: Graph, clause_index: dict[str, tuple[str, str]]) -> Graph:
    linked = Graph()
    for subj, pred, obj in graph:
        if pred == SKOS.definition and isinstance(obj, Literal) and is_text_literal(obj):
            linked_text = linkify_definition(str(obj), clause_index)
            obj = Literal(linked_text, lang=obj.language or DEFAULT_LANG)
        linked.add((subj, pred, obj))
    linked.bind("dcterms", DCTERMS)
    linked.bind("skos", SKOS)
    linked.bind("vann", VANN)
    linked.bind("cc", CC)
    return linked


def tag_plain_literals(graph: Graph) -> Graph:
    tagged = Graph()
    for subj, pred, obj in graph:
        if isinstance(obj, Literal):
            obj = tag_literal(obj)
        tagged.add((subj, pred, obj))
    tagged.bind("dcterms", DCTERMS)
    tagged.bind("skos", SKOS)
    tagged.bind("vann", VANN)
    tagged.bind("cc", CC)
    return tagged


def normalize_graph(graph: Graph) -> Graph:
    normalized = Graph()
    for subj, pred, obj in graph:
        subj = normalize_uri(subj) if isinstance(subj, URIRef) else subj
        obj = normalize_uri(obj) if isinstance(obj, URIRef) else obj
        normalized.add((subj, pred, obj))
    normalized.bind("dcterms", DCTERMS)
    normalized.bind("skos", SKOS)
    normalized.bind("vann", VANN)
    normalized.bind("cc", CC)
    return normalized


def local_name(uri: URIRef | str) -> str | None:
    text = str(uri)
    if text.startswith(BASE):
        return text[len(BASE) :]
    if "://" not in text:
        return text
    return None


def insert_spaces(name: str) -> str:
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", name)
    spaced = re.sub(r"([a-z\d])([A-Z])", r"\1 \2", spaced)
    return spaced


def collection_title(name: str) -> str:
    title = insert_spaces(name)
    if title.endswith(" Terms"):
        return title[0].upper() + title[1:]
    if title.endswith("Terms"):
        return title[:-5] + " Terms"
    return title[0].upper() + title[1:] if title else title


def is_group_collection(member_names: list[str]) -> bool:
    return bool(member_names) and all(name.endswith("Terms") for name in member_names)


def load_graph(owl_path: Path) -> Graph:
    content = owl_path.read_text(encoding="utf-8")
    content = content.replace(" xml:", " xmlns:")
    content = content.replace('rdf:about=":', 'rdf:about="')
    content = content.replace('rdf:resource=":', 'rdf:resource="')
    graph = Graph()
    graph.parse(data=content, format="xml", base=BASE)
    return graph


def build_collections(graph: Graph) -> dict[str, list[str]]:
    collections: dict[str, list[str]] = {}
    for coll in graph.subjects(RDF.type, SKOS.Collection):
        name = local_name(coll)
        if not name:
            continue
        members = []
        for member in graph.objects(coll, SKOS.member):
            member_name = local_name(member)
            if member_name:
                members.append(member_name)
        collections[name] = members
    return collections


def classify_collections(collections: dict[str, list[str]]) -> tuple[set[str], set[str]]:
    groups = set()
    patterns = set()
    for name, members in collections.items():
        if is_group_collection(members):
            groups.add(name)
        else:
            patterns.add(name)
    return groups, patterns


def pattern_member_classes(collections: dict[str, list[str]], patterns: set[str]) -> dict[str, set[URIRef]]:
    mapping: dict[str, set[URIRef]] = {}
    for pattern in patterns:
        members = {NS[name] for name in collections[pattern]}
        mapping[pattern] = members
    return mapping


def is_property_uri(graph: Graph, uri: URIRef) -> bool:
    if not isinstance(uri, URIRef):
        return False
    if local_name(uri) is None:
        return False
    for prop_type in (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty):
        if (uri, RDF.type, prop_type) in graph:
            return True
    return False


def collect_reachable(graph: Graph, seeds: set[URIRef | BNode]) -> Graph:
    sub = Graph()
    sub.bind("dcterms", DCTERMS)
    sub.bind("skos", SKOS)
    queue = list(seeds)
    seen: set[URIRef | BNode] = set()
    while queue:
        node = queue.pop()
        if node in seen:
            continue
        seen.add(node)
        for pred, obj in graph.predicate_objects(node):
            sub.add((node, pred, obj))
            if isinstance(obj, BNode) and obj not in seen:
                queue.append(obj)
            if isinstance(node, BNode):
                for subj, p2, o2 in graph.subject_objects(node):
                    sub.add((subj, p2, o2))
                    if isinstance(subj, BNode) and subj not in seen:
                        queue.append(subj)
    return sub


def property_definition_triples(graph: Graph, prop: URIRef) -> Graph:
    sub = Graph()
    for pred, obj in graph.predicate_objects(prop):
        sub.add((prop, pred, obj))
    return sub


def properties_used_in(subgraph: Graph, full_graph: Graph) -> set[URIRef]:
    used: set[URIRef] = set()
    for subj, pred, obj in subgraph:
        if is_property_uri(full_graph, pred):
            used.add(pred)
        if isinstance(obj, URIRef) and is_property_uri(full_graph, obj):
            used.add(obj)
        if pred in {OWL.onProperty, OWL.onClass, OWL.allValuesFrom, OWL.someValuesFrom, OWL.hasValue}:
            if isinstance(obj, URIRef) and is_property_uri(full_graph, obj):
                used.add(obj)
    return used


def bind_namespaces(graph: Graph) -> None:
    graph.bind("", NS)
    graph.bind("dcterms", DCTERMS)
    graph.bind("skos", SKOS)
    graph.bind("vann", VANN)
    graph.bind("cc", CC)
    graph.bind("xsd", XSD)


def convert_vocab_iris_to_prefixed(body: str) -> str:
    """Convert <localName> to :localName outside of string literals."""
    vocab_iri = re.compile(r"<([A-Za-z][A-Za-z0-9_-]*)>")
    result: list[str] = []
    i = 0
    length = len(body)

    while i < length:
        char = body[i]
        if char == '"':
            if i + 2 < length and body[i : i + 3] == '"""':
                end = body.find('"""', i + 3)
                if end == -1:
                    result.append(body[i:])
                    break
                result.append(body[i : end + 3])
                i = end + 3
                continue

            end = i + 1
            while end < length:
                if body[end] == "\\":
                    end += 2
                    continue
                if body[end] == '"':
                    end += 1
                    break
                end += 1
            result.append(body[i:end])
            i = end
            continue

        match = vocab_iri.match(body, i)
        if match:
            result.append(f":{match.group(1)}")
            i = match.end()
            continue

        result.append(char)
        i += 1

    return "".join(result)


def prettify_turtle(body: str) -> str:
    body = re.sub(r"\^\^<xsd:([^>]+)>", r"^^xsd:\1", body)
    body = re.sub(r"<xsd:([^>]+)>", r"xsd:\1", body)
    return convert_vocab_iris_to_prefixed(body)


def serialize_body(graph: Graph) -> str:
    if len(graph) == 0:
        return ""
    body_graph = Graph()
    body_graph += graph
    bind_namespaces(body_graph)
    body = body_graph.serialize(format="turtle", base=BASE)
    lines = body.splitlines()
    start = 0
    for idx, line in enumerate(lines):
        if line.startswith("@prefix") or line.startswith("@base") or line.startswith("BASE") or line.startswith("PREFIX"):
            continue
        start = idx
        break
    return prettify_turtle("\n".join(lines[start:]).strip())


def format_imports(import_files: list[str], terminal: bool = True) -> str:
    if not import_files:
        return ""
    if len(import_files) == 1:
        end = " ." if terminal else " ;"
        return f"    owl:imports <{import_files[0]}>{end}"
    lines = ["    owl:imports"]
    for idx, filename in enumerate(import_files):
        if idx == len(import_files) - 1:
            end = " ." if terminal else " ;"
            lines.append(f"        <{filename}>{end}")
        else:
            lines.append(f"        <{filename}> ,")
    return "\n".join(lines)


def ontology_subject(ontology_name: str) -> str:
    return ":" if not ontology_name else f":{ontology_name}"


def write_ttl(
    path: Path,
    ontology_name: str,
    title: str,
    import_files: list[str],
    body_graph: Graph,
    modified: str,
    extra_comment: str | None = None,
    extra_triples: list[tuple] | None = None,
) -> None:
    subject = ontology_subject(ontology_name)
    body = serialize_body(body_graph)
    parts = [
        PREFIXES.rstrip(),
        "",
        f"{subject} a owl:Ontology ;",
        f'    dcterms:title "{title}"@{DEFAULT_LANG} ;',
        f'    dcterms:modified "{modified}"^^xsd:date ;',
    ]
    if extra_triples:
        for pred, obj in extra_triples:
            parts.append(format_predicate_object(pred, obj, terminal=False))
    if import_files:
        parts.append(format_imports(import_files, terminal=True))
    else:
        parts[-1] = parts[-1].rstrip(" ;") + " ."
    if extra_comment:
        parts.extend(["", extra_comment])
    if body:
        parts.extend(["", body, ""])
    path.write_text("\n".join(parts), encoding="utf-8")


def format_predicate_object(pred, obj, terminal: bool = False) -> str:
    end = " ." if terminal else " ;"
    n3m = _n3_manager()
    pred_n3 = pred.n3(namespace_manager=n3m)
    if isinstance(obj, Literal):
        return f"    {pred_n3} {serialize_literal_ttl(obj)}{end}"
    if isinstance(obj, URIRef):
        return f"    {pred_n3} {obj.n3(namespace_manager=n3m)}{end}"
    return f"    {pred} {obj}{end}"


def _n3_manager():
    from rdflib.namespace import NamespaceManager

    graph = Graph()
    bind_namespaces(graph)
    return graph.namespace_manager


def serialize_literal_ttl(literal: Literal) -> str:
    if literal.datatype:
        dt = str(literal.datatype)
        if dt.startswith(str(XSD)) or dt.startswith("xsd:"):
            local = dt.rsplit("#", 1)[-1].split(":")[-1]
            return f'"{literal}"^^xsd:{local}'
        return f'"{literal}"^^{dt}'
    lang_suffix = f"@{literal.language}" if literal.language else f"@{DEFAULT_LANG}"
    escaped = collapse_literal_whitespace(str(literal)).replace('"', '\\"')
    return f'"{escaped}"{lang_suffix}'


def write_master_ttl(
    path: Path,
    ontology_uri: URIRef,
    import_files: list[str],
    metadata: list[tuple],
    modified: str,
) -> None:
    lines = [
        PREFIXES.rstrip(),
        "",
        ": a owl:Ontology ;",
        '    dcterms:title "METR Vocabulary"@en ;',
    ]
    for pred, obj in metadata:
        if pred == DCTERMS.title:
            continue
        if pred == DCTERMS.modified:
            continue
        if isinstance(obj, Literal):
            lines.append(f"    {pred.n3(namespace_manager=_n3_manager())} {serialize_literal_ttl(obj)} ;")
        elif isinstance(obj, URIRef):
            term = obj.n3(namespace_manager=_n3_manager())
            lines.append(f"    {pred.n3(namespace_manager=_n3_manager())} {term} ;")
    lines.append(f'    dcterms:modified "{modified}"^^xsd:date ;')
    lines.append(format_imports(import_files, terminal=True))
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("docs/itsVocabulary.owl"),
        help="Source OWL file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs"),
        help="Directory for generated Turtle files",
    )
    args = parser.parse_args()

    graph = normalize_graph(load_graph(args.input))
    graph = tag_plain_literals(graph)
    graph = linkify_definitions(graph, build_clause_index(graph))
    collections = build_collections(graph)
    groups, patterns = classify_collections(collections)
    pattern_classes = pattern_member_classes(collections, patterns)

    modified = date.today().isoformat()

    # Build pattern subgraphs and track property usage.
    pattern_graphs: dict[str, Graph] = {}
    property_patterns: dict[URIRef, set[str]] = defaultdict(set)

    for pattern_name, class_uris in pattern_classes.items():
        subgraph = collect_reachable(graph, class_uris)
        pattern_graphs[pattern_name] = subgraph
        for prop in properties_used_in(subgraph, graph):
            if (prop, RDF.type, OWL.AnnotationProperty) in graph:
                continue
            property_patterns[prop].add(pattern_name)

    core_graph = Graph()
    core_graph.bind("dcterms", DCTERMS)
    core_graph.bind("skos", SKOS)

    for subj, pred, obj in graph:
        if (subj, RDF.type, OWL.AnnotationProperty) in graph:
            core_graph += property_definition_triples(graph, subj)
        elif (subj, RDF.type, OWL.ObjectProperty) in graph or (subj, RDF.type, OWL.DatatypeProperty) in graph:
            if len(property_patterns.get(subj, set())) != 1:
                core_graph += property_definition_triples(graph, subj)

    for pattern_name, subgraph in pattern_graphs.items():
        pattern_props = Graph()
        for prop, used_in in property_patterns.items():
            if used_in == {pattern_name}:
                pattern_props += property_definition_triples(graph, prop)
        pattern_graphs[pattern_name] = pattern_props + subgraph

    args.output_dir.mkdir(parents=True, exist_ok=True)

    write_ttl(
        args.output_dir / "core.ttl",
        "core",
        "METR Vocabulary Core",
        [],
        core_graph,
        modified,
        "# Annotation properties and shared datatype/object properties",
    )

    for pattern_name in sorted(patterns):
        write_ttl(
            args.output_dir / f"{pattern_name}-pattern.ttl",
            pattern_name,
            collection_title(pattern_name),
            ["core.ttl"],
            pattern_graphs[pattern_name],
            modified,
        )

    for group_name in sorted(groups):
        child_imports = sorted(
            f"{member}-pattern.ttl" if member in patterns else f"{member}-group.ttl"
            for member in collections[group_name]
        )
        write_ttl(
            args.output_dir / f"{group_name}-group.ttl",
            group_name,
            collection_title(group_name),
            ["core.ttl", *child_imports],
            Graph(),
            modified,
        )

    top_level_groups = sorted(
        member
        for member in collections.get("terms", [])
        if member in groups
    )
    if "terms" in groups:
        terms_child_imports = [f"{name}-group.ttl" for name in top_level_groups]
        write_ttl(
            args.output_dir / "terms-group.ttl",
            "terms",
            collection_title("terms"),
            ["core.ttl", *terms_child_imports],
            Graph(),
            modified,
        )

    master_metadata = []
    ontology_uri = URIRef(BASE)
    for pred, obj in graph.predicate_objects(ontology_uri):
        if pred in MASTER_ONTOLOGY_TRIPLES:
            master_metadata.append((pred, obj))

    master_imports = ["core.ttl", *[f"{name}-group.ttl" for name in sorted(groups)]]
    write_master_ttl(
        args.output_dir / "itsVocabulary.ttl",
        ontology_uri,
        master_imports,
        master_metadata,
        modified,
    )

    print(
        f"Generated core.ttl, itsVocabulary.ttl, {len(patterns)} pattern files, "
        f"and {len(groups) + (1 if 'terms' in groups else 0)} group files in {args.output_dir}"
    )
    print(f"Pattern collections: {len(patterns)}")
    print(f"Group collections: {len(groups)}")


if __name__ == "__main__":
    main()
