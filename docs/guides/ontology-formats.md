# Ontology File Formats and Annotations

## General

This repository maintains the ISO 24315 METR vocabulary using technologies chosen for version control, formal semantics, and automated website generation:

| Technology | Purpose |
|------------|---------|
| **GitHub** | Version control, reviews, issues, releases |
| **OWL 2** | Class/property semantics and imports |
| **W3C Turtle (`.ttl`)** | Authoritative serialization ([details](turtle.md)) |
| **`docs/python/ttl2mkdocs.py`** | Convert Turtle into Markdown, diagrams, and MkDocs navigation ([script README](../python/README.md)) |
| **Graphviz** | Render concept diagrams from generated DOT |
| **Material for MkDocs** | Build the public documentation site |

ISO 24315 is a **single vocabulary project** (`iso24315-vocab`) with one namespace and many modular Turtle files under `docs/`.

## Repository organization

| Artifact | Convention |
|----------|------------|
| GitHub repository | `ISO-TC204/iso24315-vocab` |
| Public site | `https://isotc204.org/iso24315` |
| Vocabulary namespace | `https://w3id.org/itsdata/metr/` |
| Master Turtle file | `docs/metrVocabulary.ttl` |

Imported W3C vocabularies (RDF, RDFS, OWL, SKOS, Dublin Core, XSD, VANN, CC) are referenced by their standard IRIs via `PREFIX` declarations. They are not copied into this repository.

## Namespaces and prefixes

| Prefix | IRI |
|--------|-----|
| `:` (default) | `https://w3id.org/itsdata/metr/` |
| `dcterms:` | `http://purl.org/dc/terms/` |
| `owl:` | `http://www.w3.org/2002/07/owl#` |
| `rdf:` | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` |
| `rdfs:` | `http://www.w3.org/2000/01/rdf-schema#` |
| `skos:` | `http://www.w3.org/2004/02/skos/core#` |
| `vann:` | `http://purl.org/vocab/vann/` |
| `xsd:` | `http://www.w3.org/2001/XMLSchema#` |
| `cc:` | `http://creativecommons.org/ns#` |

Each Turtle file **should** begin with `BASE <https://w3id.org/itsdata/metr/>` and matching `PREFIX : <...>`.

## Ontology (module) annotations

### Master ontology (`metrVocabulary.ttl`)

Recommended annotations, in roughly this order:

| Annotation | Usage |
|------------|--------|
| `dcterms:title` | Site / vocabulary name |
| `dcterms:description` | Home-page summary (Markdown links allowed) |
| `dcterms:license` | Legal terms (CC BY 4.0 is used) |
| `cc:attributionName` | Attribution text |
| `vann:preferredNamespacePrefix` | Preferred short prefix (`metrVocab`) |
| `dcterms:creator` | Primary author(s) |
| `dcterms:issued` | Issue / publication date for this formalization |
| `dcterms:modified` | Last modification date |
| `owl:versionInfo` | Semantic version string |
| `owl:versionIRI` | Version IRI for the release |
| `rdfs:comment` | Optional human-readable version history notes |
| `owl:imports` | `core.ttl` and every top-level `*-group.ttl` |

### Group and pattern ontologies

| Annotation | Usage |
|------------|--------|
| `dcterms:title` | **Required** for navigation and page headings |
| `dcterms:modified` | Date of last edit to the module |
| `owl:imports` | Patterns import `core.ttl`; groups import their patterns (and optionally `core.ttl`) |

## Annotations for terms (classes)

### Required / strongly expected

| Annotation | Usage |
|------------|--------|
| `skos:prefLabel` | Preferred term; used as the page title and primary display name. |
| `skos:definition` | Normative definition. Prefer markdown links to other terms where useful. |
| `:clause` | Clause number in the ISO vocabulary structure. Declared in `core.ttl`. |

### Recommended as needed

| Annotation | Usage |
|------------|--------|
| `:altPrefLabel` | Alternative preferred term |
| `skos:altLabel` | Admitted term |
| `skos:hiddenLabel` | Deprecated or hidden term |
| `skos:note` | Informative note to entry; repeatable |
| `skos:example` | EXAMPLE material; repeatable |
| `skos:historyNote` | Introduction / change history relative to ISO editions |
| `dcterms:source` | Bibliographic or normative source text |
| `rdfs:subClassOf` | Hierarchical specialization (URI or restriction) |
| `owl:disjointWith` | Disjointness axioms when required |

### Clause numbering rules

- All terms in a **pattern** should share the same parent clause.
- Final segments under that parent should be **contiguous** (no gaps or duplicates).
- Patterns within a **group** should likewise share a common root and use sequential numbering at the pattern level.

## Formatting policies for definitions

- Write definitions so they work as ISO vocabulary entries (genus + differentia where practical).
- When referring to other defined terms, use markdown links that the tooling and site can resolve (for example `[rule](rule.md)`).
- Keep one primary `skos:definition` per language; put elaboration in `skos:note` or `skos:example`.
