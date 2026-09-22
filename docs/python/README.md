# ttl2mkdocs — Website generation for ISO 24315

This directory contains the Python toolchain that builds the MkDocs site (term pages, group/pattern pages, concept diagrams, and navigation) from the modular Turtle ontology in `docs/`.

`csv_to_ttl.py` converts the original `Vocab.csv` source into the modular Turtle files. After that initial conversion, Turtle is the editorial source of truth.

The main website entry point is `ttl2mkdocs.py`. Supporting modules:

| Module | Role |
|--------|------|
| `ontology_processor_ttl.py` | Discover modules, load the unified graph, registries, clause validation |
| `markdown_generator.py` | Term/group/pattern/index Markdown and `mkdocs.yml` nav updates |
| `diagram_generator.py` | Graphviz DOT / SVG / PNG concept diagrams |
| `utils.py` | Labels, breadcrumbs, page-feedback links, helpers |
| `split_ontology.py` | Utility for splitting / linkifying ontology content |
| `fields.py` | Shared field helpers |
| `csv_to_ttl.py` | Convert `Vocab.csv` into modular Turtle files |

These scripts follow the ISO 14812 `ttl2mkdocs` toolchain and are specialized for vocabulary groups/patterns, clause numbers, and SKOS-oriented term pages.

## Prerequisites

Run the script from the **repository root** (the directory that contains `mkdocs.yml` and `docs/`).

| Requirement | Purpose |
|-------------|---------|
| `mkdocs.yml` | Site configuration; `nav` under **Vocabulary** is rewritten each run |
| `docs/` | Source `.ttl` files and generated Markdown / diagrams |
| `docs/metrVocabulary.ttl` | Master ontology (required) |
| Python 3 | Runtime |
| [RDFLib](https://rdflib.readthedocs.io/) | Parse and query Turtle |
| [Graphviz](https://graphviz.org/) (`dot` on `PATH`) | Render class diagrams |
| PyYAML | Read/write `mkdocs.yml` |

Minimum Python dependencies:

```bash
pip install rdflib pyyaml
```

Graphviz must be installed as a system package so the `dot` executable is available. For local site preview, also install [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) and any plugins listed in `mkdocs.yml`.

## Usage

```bash
cd /path/to/iso24315-vocab
python docs/python/csv_to_ttl.py
PYTHONPATH=docs/python python docs/python/ttl2mkdocs.py
```

With a project virtual environment:

```bash
PYTHONPATH=docs/python .venv/bin/python docs/python/ttl2mkdocs.py
```

No command-line flags are accepted. Extra arguments print usage and exit with code `1`.

### Exit behavior

| Situation | Result |
|-----------|--------|
| Missing `mkdocs.yml` or `docs/` | Error message, exit `1` |
| Missing `docs/metrVocabulary.ttl` or failed vocabulary load | Error, exit `1` |
| Per-class / diagram / write errors | Logged into an errors list; processing continues where possible |
| Warnings only (for example clause gaps) | Printed during the run and again in the **RUN SUMMARY**; exit `0` |
| One or more errors | **RUN SUMMARY** lists them; exit `1` |

At the end of every run, warnings and errors are reprinted in a `RUN SUMMARY` block on stderr so they are easy to find after long generation logs.

## Turtle files in `docs/`

All Turtle modules reachable from `metrVocabulary.ttl` via `owl:imports` are loaded into one **unified RDF graph**. Classification is by basename:

| Pattern | Example | Role |
|---------|---------|------|
| `metrVocabulary.ttl` | — | **Master** — home metadata, versioning, imports groups |
| `core.ttl` | — | **Core** — shared properties; not a nav group/pattern |
| `terms-group.ttl` | — | **Terms hub** — anchors Vocabulary navigation |
| `*-group.ttl` | `vehicleTerms-group.ttl` | **Group** — overview page listing patterns |
| `*-pattern.ttl` | `travellerTerms-pattern.ttl` | **Pattern** — overview page + member term pages |

Editorial conventions for file and concept names are in [../guides/naming-conventions.md](../guides/naming-conventions.md). Annotation expectations are in [../guides/ontology-formats.md](../guides/ontology-formats.md).

### Namespace and local concepts

The vocabulary namespace is fixed as `https://w3id.org/itsdata/metr/` (`BASE` in the Turtle files).

Only classes in that namespace that are treated as publishable terms receive individual Markdown pages. Display names come from `skos:prefLabel` (via `get_label` in `utils.py`). Page filenames use the preferred label (for example `docs/terms/road vehicle.md`).

### Recommended annotations the scripts rely on

**On module ontologies**

| Property | Used for |
|----------|----------|
| `dcterms:title` | Group/pattern titles and nav labels |
| `dcterms:description` | Master home text (and optional module blurbs) |
| `dcterms:modified` | Provenance on modules |

**On term classes**

| Property | Used for |
|----------|----------|
| `skos:prefLabel` | Page title and links |
| `skos:definition` | Lead definition |
| `:clause` | Clause line, sorting, pattern/group parent clause |
| `:altPrefLabel`, `skos:altLabel`, `skos:hiddenLabel` | Alternate / admitted / deprecated terms |
| `skos:note`, `skos:example`, `skos:historyNote` | Notes, examples, history |
| `dcterms:source` | Source line |
| `rdfs:subClassOf`, `owl:disjointWith`, property restrictions | Diagrams and “Relationships” tables |

### Clause validation

After patterns are collected, the processor warns when:

- members of a pattern or group do not share the same root clause;
- clause numbers overlap; or
- clause numbers under a shared root are not contiguous.

These warnings appear inline and again in the run summary.

### Page feedback links

Generated pages include a **Comment on this page** footer that opens a GitHub issue using `.github/ISSUE_TEMPLATE/page-feedback.yml`, prefilling page title and path. The repository URL is taken from `mkdocs.yml` `repo_url`.

### owl:imports

Imports are followed from the master file using **relative** Turtle references (for example `<vehicleTerms-group.ttl>`). HTTP imports are skipped during discovery so generation does not depend on network access for this vocabulary’s own modules.

## What the script generates

From the repository root, under `docs/`:

| Output | Description |
|--------|-------------|
| `index.md` | Site home from master ontology metadata (**overwrites** this file) |
| `terms/<prefLabel>.md` | One page per publishable term |
| `terms/groups/<Group Title>.md` | Group overview (patterns listed by parent clause) |
| `terms/patterns/<Pattern Title>.md` | Pattern overview (terms listed by clause) |
| `terms/concept_registry.md` | Alphabetical registry table |
| `diagrams/<term>.dot` / `.svg` / `.png` | Concept diagrams |
| `mkdocs.yml` `nav` | Leading ISO / TC 204 links preserved; generated tree nested under **Vocabulary** |

### Navigation structure written to `mkdocs.yml`

```yaml
nav:
- TC204 on ISO.org: https://www.iso.org/committee/54706.html
- TC 204 Home: https://isotc204.org/
- Guides:
  - Overview: guides/index.md
  - Naming Conventions: guides/naming-conventions.md
  - Ontology Formats: guides/ontology-formats.md
  - Turtle: guides/turtle.md
  - Website Generation: python/README.md
- Vocabulary:
  - Home: index.md
  - Alphabetical Listing: terms/concept_registry.md
  - <Group>:
    - terms/groups/<Group>.md
    - <Pattern>:
      - terms/patterns/<Pattern>.md
      - <term>: terms/<term>.md
```

Any top-level nav entries before `Vocabulary` other than `Guides` are preserved when present; otherwise the two ISO/TC 204 links above are used as defaults. The **Guides** section is always rewritten to the canonical contributor-doc list.

## Typical workflow

1. Edit or add Turtle under `docs/` (prefer copying an existing `*-pattern.ttl` as a template).
2. Ensure the new pattern is imported by its group, and the group by `metrVocabulary.ttl` if needed.
3. From the repository root, run:

   ```bash
   PYTHONPATH=docs/python python docs/python/ttl2mkdocs.py
   ```

4. Review the **RUN SUMMARY** for clause or processing issues.
5. Inspect generated Markdown under `docs/terms/` and diagrams under `docs/diagrams/`.
6. Preview with `mkdocs serve` (or build/deploy via your usual MkDocs / CI process).

## Sample module layout

```text
docs/
├── metrVocabulary.ttl             # master
├── core.ttl                       # shared properties
├── terms-group.ttl                # nav hub
├── vehicleTerms-group.ttl         # group
│     imports vehicleComponentTerms-pattern.ttl, ...
├── vehicleComponentTerms-pattern.ttl
├── travellerTerms-pattern.ttl
└── python/
      └── ttl2mkdocs.py            # this toolchain
```
