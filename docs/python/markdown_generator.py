import os
import logging
import yaml
import re
import traceback
from collections import defaultdict
from rdflib import Graph, XSD, Literal, URIRef, OWL, RDFS, RDF
from rdflib.namespace import DCTERMS, SKOS
from ontology_processor_ttl import (
    BASE,
    parent_clause_from_class_entries,
    collection_clause_sort_key,
    collection_title,
    import_module_name,
)
from utils import (
    get_label,
    get_property_info,
    get_qname,
    get_first_literal,
    get_class_expression_str,
    insert_spaces,
    class_restrictions,
    iter_annotations,
    DESC_PROPS,
    get_ontology_for_uri,
    fauxClass,
    get_filename,
    TERMS_SUBDIR,
    GROUPS_SUBDIR,
    PATTERNS_SUBDIR,
    term_nav_path,
    term_page_link,
    term_page_filename,
    diagram_path_from_terms,
    md_table_delimiter,
    concept_registry_nav_path,
    collection_list_item,
    group_nav_path,
    pattern_nav_path,
    group_page_filename,
    pattern_page_filename,
    term_breadcrumb,
    group_breadcrumb,
    pattern_breadcrumb,
    index_breadcrumb,
    page_feedback_markup,
    group_nav_path,
    pattern_nav_path,
    term_nav_path,
    concept_registry_nav_path,
)

log = logging.getLogger("ttl2mkdocs")

class SafeMkDocsLoader(yaml.SafeLoader):
    """Custom YAML loader to handle MkDocs-specific python/name tags."""
    def ignore_python_name(self, node):
        """Treat python/name tags as strings."""
        return self.construct_scalar(node)

yaml.SafeLoader.add_constructor('tag:yaml.org,2002:python/name:material.extensions.emoji.twemoji', SafeMkDocsLoader.ignore_python_name)
yaml.SafeLoader.add_constructor('tag:yaml.org,2002:python/name:pymdownx.superfences.fence_code_format', SafeMkDocsLoader.ignore_python_name)
yaml.SafeLoader.add_constructor('tag:yaml.org,2002:python/name:material.extensions.emoji.to_svg', SafeMkDocsLoader.ignore_python_name)

def get_specializations(
    g: Graph,
    cls: URIRef,
    global_term_labels: set,
    ns: str,
    prefix_map: dict,
    ns_to_ontology: dict,
) -> list:
    """Find all subclasses (direct and indirect) of the given class."""
    specializations = []
    visited = set()

    def collect_subclasses(c):
        if c in visited:
            return
        visited.add(c)
        for s in g.subjects(RDFS.subClassOf, c):
            if not isinstance(s, URIRef) or s == c:
                continue
            label = get_label(g, s)
            if not label or label not in global_term_labels:
                collect_subclasses(s)
                continue
            ont = get_ontology_for_uri(str(s), ns_to_ontology)
            if ont:
                desc = get_first_literal(g, s, [SKOS.definition]) or get_first_literal(g, s, [DCTERMS.description]) or ""
                specializations.append((label, desc, ont))
            collect_subclasses(s)

    collect_subclasses(cls)
    log.debug(f"Specializations for {cls}: {specializations}")
    return sorted(specializations, key=lambda x: x[0].lower())

def get_used_by(cls: str, prop_list: list):
    used_by = []
    log.debug(f"length of prop_list: {len(prop_list)}")
    for item in prop_list:
        if len(item) != 3:
            continue
        using_cls, prop_name, target_class = item
        if target_class == cls:
            used_by.append((using_cls, prop_name))
            log.debug(f"Found usage: {using_cls} uses {cls} via {prop_name}")
    return sorted(set(used_by))

def generate_prop_list(g: Graph, global_all_class_uris: set, ns: str, prefix_map: dict):
    """Generate property list for all classes."""
    prop_list = []
    for cls in sorted(global_all_class_uris):
        cls_uri = URIRef(cls)
        # Formalization section with superclasses and disjoints
        for restriction in g.objects(cls_uri, RDFS.subClassOf):
            if (restriction, RDF.type, OWL.Restriction) in g:
                prop = g.value(restriction, OWL.onProperty)
                target_class = g.value(restriction, OWL.onClass)
                if prop and target_class:
                    prop_name, _, _ = get_property_info(g, prop, ns, prefix_map)
#                    target_id, _, _, target_qname, reflexive, _ = get_target_info(g, target_expr, cls_name, ns, prefix_map)
#                   range_name = get_class_expression_str(g, range_expr, ns, prefix_map)
                    prop_list.append((str(cls), prop_name, get_label(g, target_class)))
        # Collect direct superclasses
        for super_cls in g.objects(cls_uri, RDFS.subClassOf):
            if isinstance(super_cls, URIRef) and super_cls != OWL.Thing:
                super_name = get_qname(g, super_cls, ns, prefix_map)
                prop_list.append((str(cls), "subClassOf", super_name))
        # Collect disjoint classes
        for disjoint_cls in g.objects(cls_uri, OWL.disjointWith):
            if isinstance(disjoint_cls, URIRef):
                disjoint_name = get_qname(g, disjoint_cls, ns, prefix_map)
                prop_list.append((str(cls), "disjointWith", disjoint_name))
    log.debug(f"Generated property list: {prop_list}")
    return prop_list

def coll_uri_to_local(coll_str: str) -> str:
    if coll_str.startswith(BASE):
        return coll_str[len(BASE) :]
    return coll_str


def ontology_description(g: Graph, local_name: str) -> str:
    ont = URIRef(BASE + local_name)
    desc = get_first_literal(g, ont, [DCTERMS.description, RDFS.comment])
    return str(desc).strip() if desc else ""


def generate_collection_pages(
    docs_dir: str,
    g: Graph,
    modules: dict,
    global_patterns: dict,
    errors: list,
    repo_url: str | None = None,
) -> None:
    """Generate index pages for ontology groups and patterns."""
    groups_dir = os.path.join(docs_dir, TERMS_SUBDIR, GROUPS_SUBDIR)
    patterns_dir = os.path.join(docs_dir, TERMS_SUBDIR, PATTERNS_SUBDIR)
    os.makedirs(groups_dir, exist_ok=True)
    os.makedirs(patterns_dir, exist_ok=True)

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

    for local_name, mod in modules.items():
        kind = mod["kind"]
        if kind not in {"group", "pattern"}:
            continue
        title = mod.get("title") or collection_title(local_name)
        coll_str = BASE + local_name
        gp = global_patterns.get(coll_str)
        if not gp:
            continue
        desc = ontology_description(g, local_name)
        try:
            if kind == "group":
                path = os.path.join(groups_dir, group_page_filename(title))
                body = group_breadcrumb(title)
                body += f"# {title}\n\n"
                if desc:
                    body += f"{desc}\n\n"
                body += "## Patterns\n\n"
                pattern_rows: list[tuple[tuple, str, str]] = []
                for sub_coll in gp.get("subcollections", []):
                    sub_local = coll_uri_to_local(sub_coll)
                    sub_mod = modules.get(sub_local)
                    if not sub_mod or sub_mod["kind"] != "pattern":
                        continue
                    sub_title = sub_mod.get("title") or collection_title(sub_local)
                    sub_gp = global_patterns.get(sub_coll, {})
                    _, parent_clause = parent_clause_from_class_entries(sub_gp.get("classes", []))
                    pattern_rows.append(
                        (
                            collection_clause_sort_key(sub_gp, global_patterns),
                            parent_clause,
                            sub_title,
                        )
                    )
                pattern_rows.sort(key=lambda row: (row[0], row[2].lower()))
                for _, parent_clause, sub_title in pattern_rows:
                    link = f"../{PATTERNS_SUBDIR}/{pattern_page_filename(sub_title)}"
                    body += collection_list_item(parent_clause, sub_title, link)
                body += page_feedback_markup(title, group_nav_path(title), repo_url)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(body)
                log.debug("Generated group page: %s", path)
            else:
                group_local = pattern_to_group.get(local_name)
                group_title = None
                if group_local:
                    group_mod = modules[group_local]
                    group_title = group_mod.get("title") or collection_title(group_local)
                path = os.path.join(patterns_dir, pattern_page_filename(title))
                body = pattern_breadcrumb(title, group_title)
                body += f"# {title}\n\n"
                if desc:
                    body += f"{desc}\n\n"
                _, pattern_clause = parent_clause_from_class_entries(gp.get("classes", []))
                if pattern_clause:
                    body += f"Clause: {pattern_clause}\n\n"
                body += "## Terms\n\n"
                for cls_data in gp.get("classes", []):
                    _, cls_name, _, clause_disp, _ = cls_data
                    if fauxClass(cls_name):
                        continue
                    link = f"../{term_page_link(cls_name)}"
                    body += collection_list_item(clause_disp, cls_name, link)
                body += page_feedback_markup(title, pattern_nav_path(title), repo_url)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(body)
                log.debug("Generated pattern page: %s", path)
        except Exception as exc:
            error_msg = (
                f"Error writing collection page for {title}: {exc}\n{traceback.format_exc()}"
            )
            errors.append(error_msg)
            log.error(error_msg)


def generate_markdown(
    g: Graph,
    cls: URIRef,
    cls_name: str,
    global_patterns: dict,
    global_all_classes: set,
    global_term_labels: set,
    ns: str,
    file_path: str,
    errors: list,
    prefix_map: dict,
    prop_list: list,
    ns_to_ontology: dict,
    class_to_onts: dict,
    term_collection_map: dict,
    repo_url: str | None = None,
):
    """Generate Markdown file for a class, including all superclasses and disjoint statements in Formalization."""
    docs_dir = os.path.dirname(file_path)
    terms_dir = os.path.join(docs_dir, TERMS_SUBDIR)
    os.makedirs(terms_dir, exist_ok=True)
    filename = os.path.join(terms_dir, term_page_filename(cls_name))
    
    log.debug(f"Writing {filename} for class {cls_name} ({cls})")
    # Check if this is a pattern class
    is_pattern = cls_name in global_patterns
    log.info(f"Generating Markdown for {'pattern' if is_pattern else 'non-pattern'} class: {cls_name}")

    if is_pattern:
        log.warning(f"Generating pattern class Markdown for {cls_name}")
        # Pattern class Markdown
#        title = f"# {insert_spaces(cls_name)}\n\n"
#        desc = get_first_literal(g, cls, [SKOS.definition]) or ""
#        log.debug(f"Pattern {cls_name} description: {desc}")
#        top_desc = f"{desc}\n\n" if desc else ""
#        members_md = "It consists of the following classes:\n\n"
#        member_tuples = global_patterns[cls_name]["classes"]
#        for mem_cls, mem_ont in sorted(member_tuples, key=lambda x: x[0].lower()):
#            if mem_cls == 'ITSThing':
#                continue
#            display_mem = insert_spaces(mem_cls)
#            if len(class_to_onts[mem_cls]) > 1:
#                display_mem += f" ({mem_ont})"
#            members_md += f"- [{display_mem}]({mem_ont}__{mem_cls}.md)\n"
#        content = title + top_desc + members_md
    else:
        # Non-pattern class Markdown
        breadcrumb = term_breadcrumb(cls_name, term_collection_map)
        title = f"# {cls_name}\n\n"
        alt_labels_md = ""
        alt_pref_label_pre = URIRef(ns + 'altPrefLabel')
        alt_pref_labels = list(g.objects(cls, alt_pref_label_pre))
        if alt_pref_labels:
            for alt_pref_label in alt_pref_labels:
                alt_labels_md += f"Alternative preferred term: {str(alt_pref_label)}\n\n"
        alt_labels = list(g.objects(cls, SKOS.altLabel))
        if alt_labels:
            for alt_label in alt_labels:
                alt_labels_md += f"Admitted term: {str(alt_label)}\n\n"
        hidden_labels = list(g.objects(cls, SKOS.hiddenLabel))
        if hidden_labels:
            for hidden_label in hidden_labels:
                alt_labels_md += f"Deprecated term: {str(hidden_label)}\n\n"
        desc = get_first_literal(g, cls, [SKOS.definition]) or ""
        log.debug(f"Class {cls_name} description: {desc}")
        top_desc = f"{desc}\n\n" if desc else ""
        notes = list(g.objects(cls, SKOS.note))
        note_md = ""
        if notes:
            for i, note in enumerate(notes, start=1):
                note_md += f"Note {i} to entry: {str(note)}\n\n"
        examples = list(g.objects(cls, SKOS.example))
        example_md = ""
        if examples:
            if len(examples) == 1:
                example_md += f"EXAMPLE: {str(examples[0])}\n\n"
            else:
                for i, example in enumerate(examples, start=1):
                    example_md += f"Example {i}: {str(example)}\n\n"
        sources = list(g.objects(cls, DCTERMS.source))
        source_md = ""
        if sources:
            for source in sources:
                source_md += f"Source: {str(source)}\n\n"
        clause_pre = URIRef(ns + 'clause')
        clause_md = f"Clause: {get_first_literal(g, cls, [clause_pre])}\n\n" if get_first_literal(g, cls, [clause_pre]) else ""
        history_md = ""
        historyNotes = list(g.objects(cls, SKOS.historyNote))
        if historyNotes:
            for hist_note in historyNotes:
                history_md += f"History note: {str(hist_note)}\n\n"
        diagram_line = f"<object type=\"image/svg+xml\" data=\"{diagram_path_from_terms(cls_name, 'dot.svg')}\">\n"
        diagram_line += f"    <img alt=\"{cls_name} Diagram\" src=\"{diagram_path_from_terms(cls_name, 'dot.png')}\" /> <!-- Fallback for non-SVG browsers -->\n"
        diagram_line += "</object>\n\n"
        
        # Specializations section
        specializations = get_specializations(g, cls, global_term_labels, ns, prefix_map, ns_to_ontology)
        specializations_md = ""
        if specializations:
            specializations_md += f"## Specializations of {cls_name}\n\n"
            specializations_md += "| Class | Description |\n"
            specializations_md += md_table_delimiter(2)
            for spec_label, spec_desc, spec_ont in specializations:
                display_spec = spec_label
                if len(class_to_onts.get(spec_label, [])) > 1:
                    display_spec += f" ({spec_ont})"
                specializations_md += f"| [{display_spec}]({term_page_link(spec_label)}) | {spec_desc} |\n"
            specializations_md += "\n"
        else:
            log.debug(f"No specializations found for {cls_name}")
        
        # Formalization section with superclasses and disjoints
        restr_rows = class_restrictions(g, cls, ns, prefix_map)
        # Collect direct superclasses
        superclasses = []
        for super_cls in g.objects(cls, RDFS.subClassOf):
            if isinstance(super_cls, URIRef) and super_cls != OWL.Thing:
                super_name = get_qname(g, super_cls, ns, prefix_map)
                superclasses.append(("subClassOf", super_name))
        # Collect disjoint classes
        disjoints = []
        for disjoint_cls in g.objects(cls, OWL.disjointWith):
            if isinstance(disjoint_cls, URIRef):
                disjoint_name = get_qname(g, disjoint_cls, ns, prefix_map)
                disjoints.append(("disjointWith", disjoint_name))
        # Combine with restrictions from class_restrictions
        formalization_rows = sorted(restr_rows + superclasses + disjoints, key=lambda x: x[0].lower())
        formalization_md = ""
        if formalization_rows:
            formalization_md += f"## Relationships for {cls_name}\n\n"
            formalization_md += "| Property | Constraint |\n"
            formalization_md += md_table_delimiter(2)
            for prop, constr in formalization_rows:
                log.debug(f"Restriction for {cls_name}: ({prop}, '{constr}')")
                formalization_md += f"| {prop} | {constr} |\n"
            formalization_md += "\n"
        
        # Used by section
        used_by = get_used_by(get_label(g, cls), prop_list)
        used_by_md = ""
        if used_by:
            used_by_md += f"## References to {cls_name}\n\n"
            used_by_md += "| Referencing Term | Type of Reference |\n"
            used_by_md += md_table_delimiter(2)
            for using_cls, used_prop in used_by:
                using_uri = URIRef(using_cls)
                using_label = get_label(g, using_uri)
#                display_used = insert_spaces(using_cls)
                used_by_md += f"| [{using_label}]({term_page_link(using_label)}) | {used_prop} |\n"
            used_by_md += "\n"
        
        # Other annotations
        other_annot_md = ""
        annotations = list(iter_annotations(g, cls, ns, prefix_map))
        for pred, val in sorted(annotations):
            if pred=='altPrefLabel' or pred=='clause' or pred=='dcterms::source' or pred=='skos::altLabel' or pred=='skos::definition' or pred=='skos::example' or pred=='skos::hiddenLabel' or pred=='skos::historyNote' or pred=='skos::note' or pred=='skos::prefLabel':
                continue  # Already handled
            else:
                other_annot_md += f"| {pred} | {val} |\n"
        log.debug(f"Other annotations for {cls_name}: {other_annot_md}")
        if other_annot_md != "":
            other_annot_head = "## Other annotations\n\n"
            other_annot_head += "| Annotation | Value |\n"
            other_annot_head += md_table_delimiter(2)
            other_annot_md = other_annot_head + other_annot_md + "\n"
        
        content = (
            breadcrumb
            + title
            + top_desc
            + diagram_line
            + clause_md
            + alt_labels_md
            + example_md
            + note_md
            + source_md
            + history_md
            + specializations_md
            + formalization_md
            + used_by_md
            + other_annot_md
        )
        content += page_feedback_markup(cls_name, term_nav_path(cls_name), repo_url)

    # Write Markdown file
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        log.debug("Generated Markdown file: %s", filename)
    except Exception as e:
        error_msg = f"Error writing Markdown for {cls_name} from {file_path}: {str(e)}\n{traceback.format_exc()}"
        errors.append(error_msg)
        log.error(error_msg)
        raise

def update_mkdocs_nav(
    mkdocs_path: str,
    global_patterns: dict,
    errors: list,
    class_to_onts: dict,
    ontology_info: dict,
    input_file: str,
    local_classes: set,
    g: Graph,
    ns: str,
    modules: dict,
):
    """Update mkdocs.yml navigation with file > pattern > class or file > class structure."""
    try:
        with open(mkdocs_path, 'r', encoding="utf-8") as f:
            config = yaml.load(f, Loader=SafeMkDocsLoader)
    except Exception as e:
        error_msg = f"Error reading mkdocs.yml: {str(e)}\n{traceback.format_exc()}"
        errors.append(error_msg)
        log.error(error_msg)
        raise

    # Preserve leading external/site links; nest generated pages under Vocabulary.
    default_external_nav = [
        {"TC204 on ISO.org": "https://www.iso.org/committee/54706.html"},
        {"TC 204 Home": "https://isotc204.org/"},
    ]
    guides_nav = {
        "Guides": [
            {"Overview": "guides/index.md"},
            {"Naming Conventions": "guides/naming-conventions.md"},
            {"Ontology Formats": "guides/ontology-formats.md"},
            {"Turtle": "guides/turtle.md"},
            {"Website Generation": "python/README.md"},
        ]
    }

    prefix_nav = list(default_external_nav)
    existing_nav = config.get("nav") or []
    if isinstance(existing_nav, list) and existing_nav:
        preserved = []
        for item in existing_nav:
            if not isinstance(item, dict) or len(item) != 1:
                break
            key = next(iter(item))
            if key == "Vocabulary":
                break
            if key == "Guides":
                continue  # replaced with canonical guides_nav below
            preserved.append(item)
        if preserved:
            prefix_nav = preserved

    prefix_nav.append(guides_nav)

    vocabulary_nav = [
        {"Home": "index.md"},
        {"Alphabetical Listing": concept_registry_nav_path()},
    ]

    file_path = input_file
    ontology_name = ontology_info[file_path]["ontology_name"]
    # Find the "Terms" top-level collection (adjust IRI if needed)
    terms_coll_str = None
    for coll_str, gp in global_patterns.items():
        if gp["name"].lower() == "terms":  # or exact match: gp["name"] == "Terms"
            terms_coll_str = coll_str
            break

    if terms_coll_str:
        # Get direct members of "Terms" (sub-collections + classes)
        terms_gp = global_patterns[terms_coll_str]

        # Build the nav directly from Terms' children (skip showing "Terms")
        top_level_items = []

        # 1. Sub-collections of Terms (groups), ordered by base clause
        group_nav_items: list[tuple[tuple, dict]] = []
        for sub_coll_str in terms_gp.get("subcollections", []):
            log.info(f"Processing sub-collection for nav: {sub_coll_str}")
            if sub_coll_str in global_patterns:
                sub_gp = global_patterns[sub_coll_str]
                display_name = insert_spaces(sub_gp["name"])
                sub_nav = build_sub_nav(
                    sub_coll_str, global_patterns, class_to_onts, ontology_name, modules
                )
                log.debug(f"Built sub-nav for {display_name}: {sub_nav}")
                if sub_nav:
                    group_key = collection_clause_sort_key(sub_gp, global_patterns)
                    group_nav_items.append(
                        (
                            group_key,
                            {display_name: [group_nav_path(sub_gp["name"]), *sub_nav]},
                        )
                    )
        group_nav_items.sort(key=lambda item: (item[0], list(item[1].keys())[0].lower()))
        top_level_items.extend(item[1] for item in group_nav_items)

        # 2. Direct classes that are members of Terms (not in any sub-collection)
        direct_classes = []
        for cls_data in terms_gp.get("classes", []):
            log.info(f"Processing direct class for nav: {cls_data}")
            cls_str, cls_name, ont, _, clause_key = cls_data
            is_in_sub = False
            for sub_coll_str in terms_gp["subcollections"]:
                sub_gp = global_patterns.get(sub_coll_str, {})
                if any(c[0] == cls_str for c in sub_gp.get("classes", [])):
                    is_in_sub = True
                    break
            if not is_in_sub and not fauxClass(cls_name):
                direct_classes.append((cls_name, ont, clause_key))

        direct_classes.sort(key=lambda x: (x[2], x[0].lower()))
        for cls_name, ont, _ in direct_classes:
            display_cls = insert_spaces(cls_name)
            top_level_items.append({display_cls: term_nav_path(cls_name)})
            log.info(f"Added top-level class to nav: {cls_name} ({display_cls})")

        vocabulary_nav.extend(top_level_items)
        config["nav"] = [*prefix_nav, {"Vocabulary": vocabulary_nav}]

    else:
        log.warning("Top-level 'Terms' collection not found – falling back to all patterns")
        config["nav"] = [*prefix_nav, {"Vocabulary": vocabulary_nav}]

    try:
        with open(mkdocs_path, 'w', encoding="utf-8") as f:
            yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)
    except Exception as e:
        error_msg = f"Error writing mkdocs.yml: {str(e)}\n{traceback.format_exc()}"
        errors.append(error_msg)
        log.error(error_msg)
        raise

def generate_index(
    docs_dir: str,
    input_file: str,
    ontology_info: dict,
    global_patterns: dict,
    errors: list,
    class_to_onts: dict,
    repo_url: str | None = None,
):
    """Generate index.md file."""
    index_path = os.path.join(docs_dir, "index.md")
    index_content = ""

    file_path = input_file
    if file_path not in ontology_info:
        error_msg = f"Skipping index.md generation for {file_path} due to earlier processing failure"
        errors.append(error_msg)
        log.error(error_msg)
        return
    filename = os.path.basename(file_path)
    title = ontology_info[file_path]["title"]
    description = ontology_info[file_path]["description"]
    patterns = sorted(ontology_info[file_path]["patterns"], key=str.lower)
    non_pattern_classes = sorted(ontology_info[file_path]["non_pattern_classes"], key=str.lower)
    index_content += index_breadcrumb()
    index_content += f"# {title}\n\n"
    if description:
        index_content += f"{description}\n\n"
    index_content += f"\nThe formal definition of the terms is available in [{os.path.splitext(filename)[1][1:].upper()} Syntax]({filename}).\n"
    index_content += page_feedback_markup(title, "index.md", repo_url)

    # Write index.md
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_content)
        log.info("Generated index.md at %s", index_path)
    except Exception as e:
        error_msg = f"Error writing index.md: {str(e)}\n{traceback.format_exc()}"
        errors.append(error_msg)
        log.error(error_msg)
        raise

def build_sub_nav(
    coll_str: str,
    global_patterns: dict,
    class_to_onts: dict,
    ontology_name: str,
    modules: dict,
) -> list:
    if coll_str not in global_patterns:
        return []
    gp = global_patterns[coll_str]
    sub_nav: list = []
    items = []
    for sub_coll in gp["subcollections"]:
        sub_gp = global_patterns.get(sub_coll, {})
        clause_key = collection_clause_sort_key(sub_gp, global_patterns)
        items.append(("coll", sub_coll, clause_key))
    for cls_data in gp["classes"]:
        cls_str, cls_name, ont, _, clause_key = cls_data
        items.append(("cls", (cls_name, ont), clause_key))
    items.sort(
        key=lambda x: (
            x[2],
            global_patterns[x[1]]["name"].lower() if x[0] == "coll" else x[1][0].lower(),
        )
    )
    for it_type, it_val, _ in items:
        if it_type == "coll":
            sub_coll_str = it_val
            sub_gp = global_patterns[sub_coll_str]
            display_pat = insert_spaces(sub_gp["name"])
            sub_sub_nav = build_sub_nav(
                sub_coll_str, global_patterns, class_to_onts, ontology_name, modules
            )
            if sub_sub_nav:
                sub_local = coll_uri_to_local(sub_coll_str)
                sub_kind = modules.get(sub_local, {}).get("kind")
                if sub_kind == "pattern":
                    pattern_index = pattern_nav_path(sub_gp["name"])
                    sub_nav.append({display_pat: [pattern_index, *sub_sub_nav]})
                else:
                    sub_nav.append({display_pat: sub_sub_nav})
        else:
            cls_name, ont = it_val
            if fauxClass(cls_name):
                continue
            display_mem = insert_spaces(cls_name)
            sub_nav.append({display_mem: term_nav_path(cls_name)})
    return sub_nav