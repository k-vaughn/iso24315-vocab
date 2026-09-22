# Ontology Serialization

## Expressing the vocabulary in Turtle

**Turtle (Terse RDF Triple Language, `.ttl`)** is the authoritative format for the ISO 24315 ontology in this repository. All editorial changes to terms, groups, and patterns are made in Turtle under `docs/`; Markdown and diagrams are generated from those files.

### What is Turtle?

Turtle is a compact, text-based syntax for RDF graphs (subject–predicate–object triples). It is a W3C standard and is widely supported by ontology editors, RDF libraries (including RDFLib), and Git-friendly workflows.

Minimal example of the style used in this project:

```turtle
BASE <https://w3id.org/itsdata/metr/>
PREFIX : <https://w3id.org/itsdata/metr/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

:metrRoleTerms a owl:Ontology ;
    dcterms:title "METR Role Terms"@en ;
    dcterms:modified "2026-09-22"^^xsd:date ;
    owl:imports <core.ttl> .

:ancillaryUser a owl:Class ;
    rdfs:subClassOf :metrUser ;
    skos:definition "[METR user](METR user.md) that is not a transport-related user"@en ;
    skos:prefLabel "ancillary user"@en ;
    :clause "3.3.1.3"@en .
```

### Why Turtle is preferred here

- **Readable diffs** — reviews and Git history stay understandable.
- **Compact** — less boilerplate than RDF/XML for large vocabularies.
- **Tooling** — RDFLib, Protégé export, and this project’s generators all consume Turtle well.
- **Alignment with SPARQL** — similar abbreviation patterns help when querying the graph.

## File roles in Turtle

| File | Contents |
|------|----------|
| `metrVocabulary.ttl` | Master ontology metadata and imports of groups |
| `core.ttl` | Shared `owl:AnnotationProperty`, object properties, datatype properties |
| `*-group.ttl` | Group ontology + `owl:imports` of patterns |
| `*-pattern.ttl` | Pattern ontology + term classes (and any pattern-local properties) |

See [naming-conventions.md](naming-conventions.md) for how these names drive automation.

## Authoring tips for this repository

1. Copy an existing pattern file as a template when adding a new coherent set of terms.
2. Assign `:clause` values that continue the parent clause sequence without gaps.
3. Use `skos:prefLabel` for the display term; keep the IRI local name in lowerCamelCase.
4. After edits, run `ttl2mkdocs.py` from the repository root and check the run summary for clause warnings.
5. Preview with `mkdocs serve` before opening a pull request.
