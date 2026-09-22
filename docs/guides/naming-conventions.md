# Naming Conventions

These conventions keep the ISO 24315 METR vocabulary consistent, readable in Git diffs, and compatible with the `ttl2mkdocs` automation that builds the website. They follow the same rules as the ISO 14812 project.

## 1. Ontology IRI and namespace

| Item | Convention |
| ---- | ---------- |
| **Namespace / BASE** | `https://w3id.org/itsdata/metr/` |
| **Default prefix** | `:` (empty) and preferred prefix `metrVocab` (`vann:preferredNamespacePrefix`) |
| **Master ontology IRI** | The master file uses `: a owl:Ontology` (empty local name → the namespace itself) |
| **Module ontology IRIs** | Each group/pattern file declares an ontology with a camelCase local name, for example `:dataTerms` or `:metrRoleTerms` |

All classes and properties in this repository **shall** use the vocabulary namespace above. Do not invent a second BASE for submodules; submodule identity is carried by the module’s `owl:Ontology` local name and `dcterms:title`, not by a separate namespace.

**Versioning** (on the master ontology in `metrVocabulary.ttl`):

- `owl:versionInfo` — semantic version string (for example `"0.1.0"`)
- `owl:versionIRI` — versioned IRI for the release
- `dcterms:modified` / `dcterms:issued` — dates as appropriate
- GitHub releases mark balloted / published snapshots

The major/minor/patch scheme for the ontology is independent of ISO standard edition numbers.

## 2. Repository and directory layout

```text
iso24315-vocab/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   └── page-feedback.yml
│   ├── workflows/
│   ├── CODEOWNERS
│   └── PULL_REQUEST_TEMPLATE.md
├── docs/
│   ├── python/                 # generation scripts (see python/README.md)
│   ├── guides/                 # this contributor documentation
│   ├── diagrams/               # generated Graphviz outputs
│   ├── stylesheets/
│   ├── javascripts/
│   ├── terms/                  # generated term, group, and pattern pages
│   │   ├── groups/
│   │   ├── patterns/
│   │   └── concept_registry.md
│   ├── metrVocabulary.ttl      # master ontology
│   ├── core.ttl                # shared properties
│   ├── *-group.ttl             # thematic groups
│   ├── *-pattern.ttl           # term patterns
│   └── index.md                # generated site home (do not hand-edit)
├── Vocab.csv                   # original tabular source used for the initial conversion
├── mkdocs.yml
├── README.md
└── ...
```

Ontology sources that drive the site **shall** live as `docs/*.ttl`. Generated Markdown under `docs/terms/` and `docs/index.md` is produced by the scripts and should not be treated as the editorial source of truth.

## 3. File naming (critical for automation)

Use **lowerCamelCase** stems with a role suffix. The generation scripts classify files by basename:

| File type | Example | Role |
|-----------|---------|------|
| Master | `metrVocabulary.ttl` | Aggregates groups; site metadata and versioning |
| Core | `core.ttl` | Shared annotation and object/datatype properties; imported by patterns |
| Terms hub | `terms-group.ttl` | Special group that anchors MkDocs navigation under Vocabulary |
| Group | `dataTerms-group.ttl` | Imports related `*-pattern.ttl` files |
| Pattern | `metrRoleTerms-pattern.ttl` | Declares the OWL classes (terms) for one coherent set |

Rules:

- Group files **shall** end with `-group.ttl`.
- Pattern files **shall** end with `-pattern.ttl`.
- The stem before the suffix **should** match the local name of the `owl:Ontology` in that file.
- Prefer relative `owl:imports` of sibling files, not absolute HTTP IRIs, so offline generation works reliably.
- Do not put spaces or underscores in filenames.

## 4. Concept naming (classes and properties)

| Concept | Local IRI style | Display label | Example |
|---------|-----------------|---------------|---------|
| **Classes (terms)** | lowerCamelCase | `skos:prefLabel` with normal English spacing | `:metrUser` / `"METR user"` |
| **Object properties** | lowerCamelCase | `rdfs:label` when useful | `:has` / `"has"` |
| **Annotation properties** | lowerCamelCase | Defined in `core.ttl` | `:clause`, `:altPrefLabel` |

**Additional rules:**

- Prefer **singular** class names, matching ISO vocabulary practice.
- The IRI local name **should** be a predictable camelCase rendering of the preferred label.
- Never use spaces or underscores in IRIs.
- Avoid encoding clause numbers or edition years in the IRI; use `:clause` and `skos:historyNote` instead.
- Multi-word preferred labels stay lowercase except where English conventions require otherwise (acronyms such as METR).

## 5. Module titles and navigation labels

Each group and pattern ontology **shall** carry:

```turtle
dcterms:title "METR Role Terms"@en ;
```

Titles are shown in MkDocs navigation and on group/pattern pages. Prefer a clear English title ending in “Terms” for vocabulary modules.

## 6. Imports and modularity

Recommended import tree:

```text
metrVocabulary.ttl
├── core.ttl
├── terms-group.ttl
├── jurisdictionalTerms-group.ttl
│   └── jurisdictionalConceptTerms-pattern.ttl → core.ttl
├── dataTerms-group.ttl
│   ├── generalDataTerms-pattern.ttl → core.ttl
│   └── ...
└── ...
```

- Patterns **shall** import `core.ttl` when they use `:clause`, `:altPrefLabel`, or other core properties.
- Groups **shall** import the patterns they contain.
- The master file **shall** import every top-level group that should appear on the site.
- Cross-references between terms in different patterns use the shared namespace; do not duplicate class declarations across files.

## 7. Website automation expectations

With these names, `ttl2mkdocs.py` can:

1. Discover modules from the master’s import list.
2. Treat each `*-pattern.ttl` as a pattern page listing member terms.
3. Treat each `*-group.ttl` as a group page listing member patterns.
4. Emit one Markdown page per publishable class under `docs/terms/`.
5. Nest generated navigation under the **Vocabulary** entry in `mkdocs.yml`.
