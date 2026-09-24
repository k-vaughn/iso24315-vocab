# utils.py
import os
import re
import logging
import traceback
from pathlib import Path
from typing import Optional, Iterable, Tuple, List
from rdflib import Graph, RDF, RDFS, OWL, URIRef, Literal, BNode
from rdflib.namespace import DC, DCTERMS, SKOS, RDFS
from urllib.parse import urlencode, urljoin

PAGE_FEEDBACK_ISSUE_TEMPLATE = "page-feedback.yml"
DEFAULT_REPOSITORY_URL = "https://github.com/ISO-TC204/iso24315-vocab"

log = logging.getLogger("ofn2mkdocs")

# -------------------- namespaces --------------------
DESC_PROPS = (DC.description, SKOS.definition, RDFS.comment, DCTERMS.description)
SKIP_IN_OTHER = set(DESC_PROPS) | {RDFS.label, DCTERMS.description, SKOS.note, SKOS.example}

def _norm_base(u: str) -> str:
    return u.rstrip('/#')

def get_prefix_named_pairs(ontology_doc, ns: str):
    """Return [{'prefix': <str>, 'uri': <str>}, ...] from funowl PrefixDeclarations,
    handling different return shapes of as_prefixes() across funowl versions."""
    pd = getattr(ontology_doc, "prefixDeclarations", None)
    if not pd:
#        log.debug("No prefix declarations found, using default namespace: %s", ns)
        return [{"prefix": "", "uri": ns}]

    ap = pd.as_prefixes()
    out = []

    if hasattr(ap, "items"):
        out = [{"prefix": str(k), "uri": str(v)} for k, v in ap.items()]
    else:
        for item in ap:
            if isinstance(item, tuple) and len(item) == 2:
                k, v = item
                out.append({"prefix": str(k), "uri": str(v)})
#                log.debug("      %s %s", k, v)
                continue

            p = (
                getattr(item, "prefixName", None)
                or getattr(item, "prefix", None)
                or getattr(item, "name", None)
            )
            iri = (
                getattr(item, "fullIRI", None)
                or getattr(item, "iri", None)
                or getattr(item, "iriRef", None)
            )
            if p is not None and iri is not None:
                out.append({"prefix": str(p), "uri": str(iri)})

    if not any(d["uri"] == ns for d in out):
        out.append({"prefix": "", "uri": ns})

#    log.debug("Prefixes extracted: %s", out)
    return out

def get_qname(g: Graph, uri, ns: str, prefix_map: dict):
    if uri is None or not str(uri).strip():
        log.error("Invalid URI provided to get_qname: %s", uri)
        return "INVALID_URI"
    s = str(uri)
    norm = _norm_base(s)
    log.debug("Processing URI: %s, normalized: %s, namespace: %s", s, norm, ns)
    full = urljoin(ns, s)
    if norm == _norm_base(ns) or full.startswith(ns):
        local = full[len(_norm_base(ns)):]
        if local.startswith(('/', '#', '_')):
            local = local[1:]
        qname = local.rstrip()
#        log.info("Matched default namespace, returning QName: %s", qname)
        return qname
    if not prefix_map:
        log.warning("Empty prefix map for URI: %s, namespace: %s", s, ns)
        return s
    for base in sorted(prefix_map.keys(), key=len, reverse=True):
        base_norm = _norm_base(base)
#        log.info("Checking prefix base: %s, normalized: %s", base, base_norm)
        if s == base or s.startswith(base) or norm == base_norm or norm.startswith(base_norm):
            local = s[len(base):]
            if local.startswith(('/', '#', '_')):
                local = local[1:]
            local = local.rstrip()
            if not local:
#                log.info("No local part after prefix %s, using base URI", base)
                local = s
            if prefix_map[base] == ":":
                qname = local
            else:
                qname = prefix_map[base] + ":" + local
            return qname
    if not s.startswith('N'):
        log.warning("No prefix found for URI: %s, namespace: %s, prefix_map:", s, ns)
        for prefix in prefix_map:
            log.info("  %s, %s", str(prefix), prefix == ns)
    return s

def get_label(g: Graph, c: URIRef) -> str:
    if c is None:
        log.error("Invalid class URI provided to get_label: None")
        return "INVALID_CLASS"
    for p in [SKOS.prefLabel, RDFS.label]:
        for _, _, lbl in g.triples((c, p, None)):
            if isinstance(lbl, Literal):
                text = str(lbl).strip()
                if text:
                    return text
    fragment_start = max(c.rfind('#'), c.rfind('/')) + 1
    return c[fragment_start:]

def get_first_literal(g: Graph, subj: URIRef, preds: Iterable[URIRef]) -> Optional[str]:
    if subj is None:
        log.error("Invalid subject URI provided to get_first_literal: None")
        return None
    for p in preds:
        for _, _, lit in g.triples((subj, p, None)):
            if isinstance(lit, Literal):
                return str(lit)
    return None

def get_ontology_metadata(g: Graph, ns: str, predicate: URIRef) -> Optional[str]:
    """Extract metadata (e.g., dc:title, dcterms:description) from any subject in the graph."""
    for subj in g.subjects(predicate=predicate):
        for _, _, lit in g.triples((subj, predicate, None)):
            if isinstance(lit, Literal):
                return str(lit)
    ontology_iri = URIRef(ns.rstrip('#/'))
    for _, _, lit in g.triples((ontology_iri, predicate, None)):
        if isinstance(lit, Literal):
            return str(lit)
    return None

def iter_annotations(g: Graph, subj: URIRef, ns: str, prefix_map: dict) -> Iterable[Tuple[str, str]]:
    """Yield (predicate_qname, literal) for annotations on subj, excluding DESC_PROPS and SKIP_IN_OTHER."""
    for p, o in sorted(g.predicate_objects(subj), key=lambda po: get_qname(g, po[0], ns, prefix_map).lower()):
        if isinstance(o, Literal) and p not in SKIP_IN_OTHER:
            yield get_qname(g, p, ns, prefix_map), str(o)

def collect_list(g: Graph, node) -> list:
    """Collect RDF list members into a Python list."""
    members = []
    while node != RDF.nil:
        first = g.value(node, RDF.first)
        if first:
            members.append(first)
        node = g.value(node, RDF.rest)
    return members

def get_class_expression_str(g: Graph, expr, ns: str, prefix_map: dict) -> str:
    """Convert complex class expression to string representation."""
    if isinstance(expr, URIRef):
        return get_qname(g, expr, ns, prefix_map)
    if isinstance(expr, BNode):
        union_col = g.value(expr, OWL.unionOf)
        if union_col and union_col != RDF.nil:
            members = collect_list(g, union_col)
            return " or ".join(sorted(get_class_expression_str(g, m, ns, prefix_map) for m in members))
        inter_col = g.value(expr, OWL.intersectionOf)
        if inter_col and inter_col != RDF.nil:
            members = collect_list(g, inter_col)
            return " and ".join(sorted(get_class_expression_str(g, m, ns, prefix_map) for m in members))
        complement = g.value(expr, OWL.complementOf)
        if complement:
            return "not " + get_class_expression_str(g, complement, ns, prefix_map)
        oneOf_members = collect_oneOf(g, expr)
        if oneOf_members:
            return "Enum: " + ", ".join(sorted(get_qname(g, m, ns, prefix_map) for m in oneOf_members))
        return "ComplexExpr"  # Fallback
    return str(expr)

def get_leaf_classes(g: Graph, expr, ns: str, prefix_map: dict) -> list:
    """Recursively get leaf classes from class expressions."""
    leaves = []
    if isinstance(expr, URIRef):
        leaves.append(expr)
    elif isinstance(expr, BNode):
        union_col = g.value(expr, OWL.unionOf)
        inter_col = g.value(expr, OWL.intersectionOf)
        complement = g.value(expr, OWL.complementOf)
        oneOf_members = collect_oneOf(g, expr)
        if union_col and union_col != RDF.nil:
            members = collect_list(g, union_col)
            for m in members:
                leaves.extend(get_leaf_classes(g, m, ns, prefix_map))
        elif inter_col and inter_col != RDF.nil:
            members = collect_list(g, inter_col)
            for m in members:
                leaves.extend(get_leaf_classes(g, m, ns, prefix_map))
        elif complement:
            leaves.extend(get_leaf_classes(g, complement, ns, prefix_map))
        elif oneOf_members:
            leaves.extend(oneOf_members)  # Treat individuals as leaves
        else:
            leaves.append(expr)  # Fallback for other BNodes
    return leaves

def collect_oneOf(g: Graph, node) -> list:
    """Collect members of owl:oneOf if present."""
    if (node, RDF.type, OWL.Class) in g:
        oneOf_col = g.value(node, OWL.oneOf)
        if oneOf_col and oneOf_col != RDF.nil:
            return collect_list(g, oneOf_col)
    return []

def class_restrictions(g: Graph, cls: URIRef, ns: str, prefix_map: dict) -> list:
    """Collect restrictions for a class, including inherited refinements."""
    rows = []
    for restr in g.objects(cls, RDFS.subClassOf):
        if (restr, RDF.type, OWL.Restriction) in g:
            prop = g.value(restr, OWL.onProperty)
            if prop:
                prop_name, is_inverse, base_prop = get_property_info(g, prop, ns, prefix_map)
                is_refined = is_refined_property(g, cls, prop, restr)
                min_card = g.value(restr, OWL.minQualifiedCardinality) or g.value(restr, OWL.minCardinality)
                max_card = g.value(restr, OWL.maxQualifiedCardinality) or g.value(restr, OWL.maxCardinality)
                card = g.value(restr, OWL.qualifiedCardinality) or g.value(restr, OWL.cardinality)
                all_values_from = g.value(restr, OWL.allValuesFrom)
                some_values_from = g.value(restr, OWL.someValuesFrom)
                has_value = g.value(restr, OWL.hasValue)
                label_parts = []
                range_expr = None
                if all_values_from:
                    range_expr = all_values_from
                    label_parts.append("all")
                if some_values_from:
                    range_expr = some_values_from
                    label_parts.append("some")
                if has_value:
                    range_expr = has_value
                    label_parts.append("has")
                if card:
                    label_parts.append(f"exactly {card}")
                if min_card:
                    label_parts.append(f"min {min_card}")
                if max_card:
                    label_parts.append(f"max {max_card}")

                # Handle unqualified cardinality by treating as qualified with owl:Thing
                if label_parts and not range_expr:
                    range_expr = OWL.Thing

                if range_expr and label_parts:
                    range_name = get_class_expression_str(g, range_expr, ns, prefix_map)
                    rows.append((prop_name, f"{' '.join(label_parts)} {range_name}"))
            else:
                rows.append(("", "Unsupported restriction"))

    return rows

def hyperlink_class(name: str, all_classes: set, ns: str):
    """Create a hyperlink only for classes in the local namespace."""
    if ':' not in name and name in all_classes:
        return f"[{name}]({term_page_link(name)})"
    return name

def fmt_title(name: str, all_classes: set, ns: str, abstract_map: dict) -> str:
    """Format class title for Graphviz, with URL attribute for local classes."""
    display_name = f"<I>{insert_spaces(name)}</I>" if abstract_map.get(name, False) else insert_spaces(name)
    return display_name

def is_abstract(cls, g, ns):
    if cls is None:
        log.error("Invalid class URI provided to is_abstract: None")
        return False
    abstract = g.value(cls, URIRef(ns + "abstract"))
    if abstract is None:
        abstract = g.value(cls, URIRef("http://protege.stanford.edu/ontologies/metadata#abstract"))
    return abstract is not None and str(abstract).lower() == "true"

def get_filename(input_string: str) -> str:
    if input_string is None:
        return None
    return input_string.replace("/", "")

TERMS_SUBDIR = "terms"
GROUPS_SUBDIR = "groups"
PATTERNS_SUBDIR = "patterns"
CONCEPT_REGISTRY_FILENAME = "concept_registry.md"


def collection_list_item(clause_display: str, label: str, link: str) -> str:
    """Markdown list item with optional leading clause number."""
    if clause_display:
        return f"- {clause_display} — [{label}]({link})\n"
    return f"- [{label}]({link})\n"


def get_repository_url(mkdocs_path: str | None = None) -> str:
    """Return the GitHub repository URL from mkdocs.yml repo_url, if set."""
    path = mkdocs_path or os.path.join(os.getcwd(), "mkdocs.yml")
    try:
        import yaml

        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        repo_url = (config.get("repo_url") or "").strip().rstrip("/")
        if repo_url:
            return repo_url
    except OSError:
        pass
    return DEFAULT_REPOSITORY_URL


def page_feedback_issue_url(
    page_title: str,
    page_path: str,
    repo_url: str | None = None,
) -> str:
    """GitHub new-issue URL for the page-feedback template with page fields prefilled."""
    base = f"{(repo_url or get_repository_url()).rstrip('/')}/issues/new"
    params = {
        "template": PAGE_FEEDBACK_ISSUE_TEMPLATE,
        "title": f"[Page feedback] {page_title}",
        "page-title": page_title,
        "page-path": page_path,
    }
    return f"{base}?{urlencode(params)}"


def page_feedback_markup(
    page_title: str,
    page_path: str,
    repo_url: str | None = None,
) -> str:
    """Horizontal rule and link inviting feedback on the current page."""
    url = page_feedback_issue_url(page_title, page_path, repo_url)
    return f"\n---\n\n[Comment on this page]({url})\n\n"


def format_breadcrumb(crumbs: list[tuple[str, str | None]]) -> str:
    """Render a breadcrumb trail; None link means current page (plain text)."""
    parts = []
    for label, link in crumbs:
        if link:
            parts.append(f"[{label}]({link})")
        else:
            parts.append(label)
    return " · ".join(parts) + "\n\n"


def group_page_filename(title: str) -> str:
    return f"{get_filename(title)}.md"


def pattern_page_filename(title: str) -> str:
    return group_page_filename(title)


def group_nav_path(title: str) -> str:
    return f"{TERMS_SUBDIR}/{GROUPS_SUBDIR}/{group_page_filename(title)}"


def pattern_nav_path(title: str) -> str:
    return f"{TERMS_SUBDIR}/{PATTERNS_SUBDIR}/{pattern_page_filename(title)}"


def group_page_link_from_terms(title: str) -> str:
    return f"{GROUPS_SUBDIR}/{group_page_filename(title)}"


def pattern_page_link_from_terms(title: str) -> str:
    return f"{PATTERNS_SUBDIR}/{pattern_page_filename(title)}"


def group_page_link_from_patterns(title: str) -> str:
    return f"../{GROUPS_SUBDIR}/{group_page_filename(title)}"


def term_breadcrumb(
    cls_name: str,
    collection_map: dict[str, dict],
) -> str:
    """Breadcrumb for a term page under docs/terms/."""
    crumbs: list[tuple[str, str | None]] = [("Home", "../index.md")]
    info = collection_map.get(cls_name)
    if info:
        if info.get("group_title"):
            crumbs.append(
                (info["group_title"], group_page_link_from_terms(info["group_title"]))
            )
        if info.get("pattern_title"):
            crumbs.append(
                (info["pattern_title"], pattern_page_link_from_terms(info["pattern_title"]))
            )
    crumbs.append((cls_name, None))
    return format_breadcrumb(crumbs)


def group_breadcrumb(group_title: str) -> str:
    return format_breadcrumb([("Home", "../../index.md"), (group_title, None)])


def pattern_breadcrumb(
    pattern_title: str,
    group_title: str | None,
) -> str:
    crumbs: list[tuple[str, str | None]] = [("Home", "../../index.md")]
    if group_title:
        crumbs.append((group_title, group_page_link_from_patterns(group_title)))
    crumbs.append((pattern_title, None))
    return format_breadcrumb(crumbs)


def registry_breadcrumb() -> str:
    return format_breadcrumb([("Home", "../index.md"), ("Alphabetical Listing", None)])


def index_breadcrumb() -> str:
    return format_breadcrumb([("Home", None)])

def concept_registry_path(docs_dir: str) -> str:
    return os.path.join(docs_dir, TERMS_SUBDIR, CONCEPT_REGISTRY_FILENAME)

def concept_registry_nav_path() -> str:
    return f"{TERMS_SUBDIR}/{CONCEPT_REGISTRY_FILENAME}"

def md_table_delimiter(column_count: int) -> str:
    """Delimiter row for GFM tables (MD060 compact style)."""
    return "|" + "|".join(" --- " for _ in range(column_count)) + "|\n"

def term_page_filename(cls_name: str) -> str:
    return f"{get_filename(cls_name)}.md"

def term_nav_path(cls_name: str) -> str:
    """MkDocs nav path relative to docs/."""
    return f"{TERMS_SUBDIR}/{term_page_filename(cls_name)}"

def term_page_link(cls_name: str) -> str:
    """Relative link between term pages in terms/."""
    return term_page_filename(cls_name)

def term_page_link_from_docs(cls_name: str) -> str:
    """Relative link from docs root (e.g. concept_registry.md)."""
    return term_nav_path(cls_name)

def diagram_path_from_terms(cls_name: str, suffix: str) -> str:
    """Relative path to a diagram asset from a term page under docs/terms/."""
    return f"../../diagrams/{get_filename(cls_name)}.{suffix}"

def term_page_dir_path(cls_name: str) -> str:
    """MkDocs directory URL path for a term page relative to docs/."""
    return f"{TERMS_SUBDIR}/{get_filename(cls_name)}/"

def term_page_link_from_diagrams(cls_name: str) -> str:
    """Relative link from diagrams/ directory (MkDocs directory URLs, trailing slash)."""
    return f"../{term_page_dir_path(cls_name)}"

def get_id(qname):
    if not qname:
        log.error("Invalid qname provided to get_id: %s", qname)
        return "INVALID_QNAME"
    if ':' in qname:
        prefix, local = qname.split(':', 1)
        return prefix + '_' + local
    return qname

def get_all_class_superclasses(cls, g):
    if cls is None:
        log.error("Invalid class URI provided to get_all_class_superclasses: None")
        return set()
    direct_supers = set()
    for super_cls in g.objects(cls, RDFS.subClassOf):
        if isinstance(super_cls, URIRef) and super_cls != OWL.Thing and (super_cls, RDF.type, OWL.Class) in g:
            direct_supers.add(super_cls)
    all_supers = set(direct_supers)
    for sup in direct_supers:
        all_supers.update(get_all_class_superclasses(sup, g))
    return all_supers

def get_property_info(g: Graph, prop: URIRef, ns: str, prefix_map: dict) -> tuple:
    """Get property name, handling inverses."""
    if not prop:
        return None, False, None
    inverse_of = g.value(prop, OWL.inverseOf)
    if inverse_of:
        base_prop = inverse_of
        is_inverse = True
        prop_name = f"inverse {get_qname(g, base_prop, ns, prefix_map)}"
        prop_label = get_label(g, base_prop)
    else:
        base_prop = prop
        is_inverse = False
        prop_name = get_qname(g, base_prop, ns, prefix_map)
    return prop_name, is_inverse, base_prop

def is_refined_property(g: Graph, cls: URIRef, prop: URIRef, restriction: URIRef) -> bool:
    """Check if a property restriction in cls refines an inherited restriction."""
    if cls is None or prop is None or restriction is None:
        log.error("Invalid input to is_refined_property: cls=%s, prop=%s, restriction=%s", cls, prop, restriction)
        return False
    all_supers = get_all_class_superclasses(cls, g)
    for super_cls in all_supers:
        for super_restr in g.objects(super_cls, RDFS.subClassOf):
            if (super_restr, RDF.type, OWL.Restriction) in g:
                super_prop = g.value(super_restr, OWL.onProperty)
                if super_prop == prop:
                    current_avf = g.value(restriction, OWL.allValuesFrom)
                    super_avf = g.value(super_restr, OWL.allValuesFrom)
                    current_card = g.value(restriction, OWL.qualifiedCardinality) or g.value(restriction, OWL.minQualifiedCardinality) or g.value(restriction, OWL.maxQualifiedCardinality)
                    super_card = g.value(super_restr, OWL.qualifiedCardinality) or g.value(super_restr, OWL.minQualifiedCardinality) or g.value(super_restr, OWL.maxQualifiedCardinality)
                    current_on_class = g.value(restriction, OWL.onClass)
                    super_on_class = g.value(super_restr, OWL.onClass)
                    if (current_avf != super_avf or
                        current_card != super_card or
                        current_on_class != super_on_class):
                        return True
    return False

def insert_spaces(name: str) -> str:
    if not name:
        log.error("Invalid name provided to insert_spaces: %s", name)
        return "INVALID_NAME"
    name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', name)
    name = re.sub(r'([a-z\d])([A-Z])', r'\1 \2', name)
    return name

def get_ontology_for_uri(uri_str: str, ns_to_ontology: dict) -> str:
    norm_uri = _norm_base(uri_str)
    for ont_ns, ont_name in sorted(ns_to_ontology.items(), key=lambda x: len(x[0]), reverse=True):
        if norm_uri.startswith(_norm_base(ont_ns)):
            return ont_name
    return None

def update_concept_registry(
    script_dir,
    registry,
    term_collection_map: dict | None = None,
    repo_url: str | None = None,
):
    root_dir = os.getcwd()
    docs_dir = os.path.join(root_dir, "docs")
    if not os.path.isdir(docs_dir):
        log.warning(f"docs directory does not exist: {docs_dir}")
    terms_dir = os.path.join(docs_dir, TERMS_SUBDIR)
    os.makedirs(terms_dir, exist_ok=True)
    registry_path = concept_registry_path(docs_dir)
    legacy_registry_path = os.path.join(docs_dir, CONCEPT_REGISTRY_FILENAME)
    if os.path.isfile(legacy_registry_path) and legacy_registry_path != registry_path:
        os.remove(legacy_registry_path)
    with open(registry_path, "w", encoding="utf-8") as f:
        f.write(registry_breadcrumb())
        f.write("# Concept Registry\n\n")
        f.write("This page lists all known terms in the METR Vocabulary.\n\n")
        f.write("| name | description |\n")
        f.write(md_table_delimiter(2))
        sorted_items = sorted(
            (info for info in registry.values() if info.get("type") == "class"),
            key=lambda info: info["name"].lower(),
        )
        for info in sorted_items:
            cls_name = info["name"]
            if not cls_name or not cls_name.strip() or fauxClass(cls_name):
                continue
            f.write(
                f"| [{cls_name}]({term_page_link(cls_name)}) | {normalize_registry_description(info['description'])} |\n"
            )
        f.write(
            page_feedback_markup(
                "Concept Registry",
                concept_registry_nav_path(),
                repo_url,
            )
        )
    log.info("Updated %s with %d entries", registry_path, len(registry))
    
def fauxClass(cls_name: str) -> bool:
    """True for RDF/OWL placeholder blank-node class names (e.g. n + hexadecimal)."""
    if not cls_name or not cls_name.strip():
        return True
    name = cls_name.strip()
    if re.fullmatch(r"N[0-9a-f]{32}", name):
        return True
    if name[0] in "Nn" and re.fullmatch(r"[0-9a-f]+", name[1:]):
        return True
    return False


def is_publishable_term(cls: URIRef, g: Graph) -> bool:
    """True when the class should have a public term page."""
    if cls is None or cls == OWL.Thing:
        return False
    label = get_label(g, cls)
    if not label or not label.strip() or label == "ITSThing":
        return False
    if fauxClass(label):
        return False
    local = str(cls).rsplit("/", 1)[-1].split("#")[-1]
    return not fauxClass(local)


def normalize_registry_description(text: str) -> str:
    """Normalize description text for the concept registry table."""
    text = normalize_string(text)
    return re.sub(r"\]\(terms/([^)]+)\)", r"](\1)", text)


def remove_placeholder_term_pages(terms_dir: str) -> int:
    """Delete generated markdown for placeholder classes."""
    removed = 0
    terms_path = Path(terms_dir)
    if not terms_path.is_dir():
        return removed
    for path in terms_path.glob("*.md"):
        if path.name == CONCEPT_REGISTRY_FILENAME:
            continue
        if path.parent != terms_path:
            continue
        if fauxClass(path.stem):
            path.unlink()
            removed += 1
    return removed

# Function to replace line returns and surrounding whitespace with a space
def normalize_string(input_str):
    lines = [line.strip() for line in input_str.splitlines()]  # Strip whitespace per line
    return ' '.join(lines)  # Join with space, collapsing empty lines