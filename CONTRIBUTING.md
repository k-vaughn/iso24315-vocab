# Contributions to this Project

## Contributions Welcome

Contributions to this project are always welcome, no matter how large or small. However, all contributing must follow the project's guidelines, conventions, and workflow.

## General Rules

This project follows ISO/TC 204 collaborative vocabulary practices. Public site: [https://isotc204.org/iso24315](https://isotc204.org/iso24315).

By providing a contribution to this project, contributors agree to submit their materials according to the project's [license](LICENSE.md) and the terms applicable to ISO vocabulary content distributed from this repository.

## Shared tooling

Version-control workflows and `scripts/versioning.py` follow the patterns maintained in
[`ISO-TC204/ontology-shared-scripts`](https://github.com/ISO-TC204/ontology-shared-scripts).
Thin workflow callers in `.github/workflows/` invoke the reusable versioning and deploy workflows from that repository.

To modify content, edit the Turtle modules under `docs/` as the source of truth and then use the website generation `ttl2mkdocs` toolchain. See [`docs/python/README.md`](docs/python/README.md). This script will convert the Turtle files into markdown format; the files are then converted into a website using mkdocs.

## Pull requests and VERSION

All changes go through pull requests. Every PR must set the root [`VERSION`](VERSION) file.

The `validate-version` check compares your PR's `VERSION` to **`RELEASES` on the upstream base branch**.

### Set VERSION

```bash
python3 scripts/versioning.py suggest --releases RELEASES
```

Ontology change (must be greater than the latest SemVer on upstream `RELEASES`):

```text
version: 0.1.1-alpha.1
```

Documentation-only (SemVer unchanged; add a date):

```text
version: 0.1.0
doc-only: 2026-09-22
```

Validate locally before opening the PR:

```bash
python3 scripts/versioning.py validate --releases RELEASES
```
