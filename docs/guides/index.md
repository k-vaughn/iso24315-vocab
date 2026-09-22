# ISO 24315 Vocabulary Ontology — Contributor Guide

This guide explains how the ISO 24315 METR vocabulary is maintained as a formal ontology and published as a website. It is aimed at editors, reviewers, and developers working in this repository.

Related pages:

- [Naming conventions](naming-conventions.md)
- [Ontology file formats and annotations](ontology-formats.md)
- [Turtle serialization](turtle.md)
- [Website generation scripts](../python/README.md)

The public site is intended to be published at [https://isotc204.org/iso24315](https://isotc204.org/iso24315). The normative content is periodically standardized in the ISO 24315 series; this GitHub project is used for collaborative maintenance and change history.

## What is an ontology?

An ontology is a formal representation of knowledge within a domain: the concepts (classes), relationships and attributes (properties), and rules that connect them. In this project the vocabulary is encoded in OWL/RDF/TTL so that:

- each term has a stable IRI and machine-readable definition;
- hierarchical and associative relationships can be expressed explicitly;
- diagrams and documentation can be generated consistently from the same source.

## Why maintain the vocabulary as an ontology?

Documenting ISO 24315 as an ontology supports:

- **Shared meaning** — preferred terms, admitted terms, definitions, and notes stay aligned across standards and implementations.
- **Traceability** — each concept carries a clause number (`:clause`) that maps to the published vocabulary structure.
- **Interoperability** — other ITS ontologies and data models can import or reference these concepts by IRI.
- **Automation** — Turtle sources drive MkDocs pages, Graphviz diagrams, and navigation without hand-maintaining hundreds of HTML pages.

## How this relates to data models and interface standards

- **Vocabulary / ontology** — defines *what terms mean* and how concepts relate (semantics).
- **Data models and interface standards** — define *how data is structured and exchanged* (syntax, fields, messages, APIs).

The ontology informs those models: a definition such as “METR rule” should mean the same thing whether it appears in a message schema, a database design, or a regulatory text.

## How the ontology is documented

| Layer | Role in this project |
| ----- | -------------------- |
| **OWL / RDF (Turtle)** | Authoritative definition of classes, properties, imports, and annotations |
| **SKOS / Dublin Core annotations** | Human-facing definitions, labels, notes, examples, provenance |
| **Clause numbers** | Alignment with the published ISO vocabulary structure |
| **MkDocs + Material** | Human-readable website |
| **Graphviz diagrams** | Concept diagrams derived from class relationships |
| **GitHub** | Version control, issues (including page feedback), and releases |

Terminology work in this project follows the spirit of ISO 704 (concept analysis, relationships, definitions, designations) and uses UML-style concept diagrams consistent with ISO 24156-1 for illustrating relationships.

This repository uses the same modular layout as [ISO 14812](https://github.com/ISO-TC204/iso14812).

## How the vocabulary is organized

This repository holds a **single vocabulary namespace** split into modular Turtle files:

1. **`metrVocabulary.ttl`** — master ontology: site title, license, versioning, and imports of all top-level groups.
2. **`core.ttl`** — shared annotation and object/datatype properties used across modules.
3. **`*-group.ttl`** — thematic collections (for example Data Terms) that import related patterns.
4. **`*-pattern.ttl`** — coherent sets of related terms (for example METR Role Terms) that declare the OWL classes.

All modules share the namespace `https://w3id.org/itsdata/metr/` (preferred prefix `metrVocab`). Local IRIs use lowerCamelCase (for example `:metrUser`); display names come from `skos:prefLabel` (for example `"METR user"`).

## Where to start

1. Read [naming conventions](naming-conventions.md) before adding files or concepts.
2. Follow [ontology formats](ontology-formats.md) for required annotations and clause numbering.
3. Author content in Turtle as described in [turtle.md](turtle.md).
4. Run the generators documented in [python/README.md](../python/README.md) and review the site locally with MkDocs.
5. Use **Comment on this page** on the published site (or open a GitHub issue with the page-feedback template) to propose corrections.
