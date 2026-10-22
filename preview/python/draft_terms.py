"""Terms whose definition differs from the last approved ontology release."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from rdflib import BNode, Graph, OWL, RDF, URIRef

log = logging.getLogger("ttl2mkdocs")

# Same stamp the ISO 24315 site uses for pages still in draft.
DRAFT_WATERMARK = '<div class="draft4-watermark" aria-hidden="true"></div>\n\n'


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _versioning():
    scripts = _repo_root() / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import versioning

    return versioning


def _git(args: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )


def approved_baseline_rev(root: Path | None = None) -> str | None:
    """Git revision of the latest ontology release that is not a pre-release.

    Prefers the ``vX.Y.Z`` tag. If the tag was not fetched, uses the release
    commit that recorded that version in ``RELEASES``.
    """
    root = root or _repo_root()
    versioning = _versioning()
    version = versioning.latest_full_ontology_version(versioning.parse_releases(root / "RELEASES"))
    if not version:
        log.info("No approved ontology release in RELEASES; draft watermarks skipped")
        return None

    tag = versioning.ontology_tag(version)
    probe = _git(["rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}"], root)
    if probe.returncode == 0 and probe.stdout.strip():
        return probe.stdout.strip()

    log.info("Tag %s not found; searching RELEASES history for %s", tag, version)
    history = _git(["log", "--format=%H", "--", "RELEASES"], root)
    if history.returncode != 0:
        log.warning("Could not read git history for RELEASES; draft watermarks skipped")
        return None

    needle = None
    for rev in reversed([line for line in history.stdout.splitlines() if line.strip()]):
        show = _git(["show", f"{rev}:RELEASES"], root)
        if show.returncode != 0:
            continue
        for line in show.stdout.splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[0] == version and parts[2] == "ontology":
                needle = rev
                break
        if needle:
            break
    if not needle:
        log.warning(
            "Approved release %s is not in git history; draft watermarks skipped",
            version,
        )
    return needle


def _load_ttl_graph(rev: str, root: Path) -> Graph:
    listing = _git(["ls-tree", "-r", "--name-only", rev, "docs"], root)
    if listing.returncode != 0:
        raise RuntimeError(listing.stderr.strip() or f"git ls-tree failed for {rev}")
    graph = Graph()
    for rel in listing.stdout.splitlines():
        if not rel.endswith(".ttl"):
            continue
        blob = subprocess.run(
            ["git", "show", f"{rev}:{rel}"],
            cwd=root,
            capture_output=True,
        )
        if blob.returncode != 0:
            continue
        graph.parse(data=blob.stdout.decode("utf-8"), format="turtle")
    return graph


def _canon(graph: Graph, node, seen: set | None = None) -> str:
    """Serialize a node so blank-node identities do not affect comparison."""
    if not isinstance(node, BNode):
        return node.n3()
    if seen is None:
        seen = set()
    if node in seen:
        return "_:cycle"
    seen = set(seen)
    seen.add(node)
    parts = [
        f"{pred.n3()} {_canon(graph, obj, seen)}"
        for pred, obj in sorted(graph.predicate_objects(node), key=lambda pair: pair[0].n3())
    ]
    return "[ " + " ; ".join(parts) + " ]"


def _term_signature(graph: Graph, term: URIRef) -> str:
    """Stable description of a term, including blank-node restrictions."""
    lines = [
        f"{pred.n3()} {_canon(graph, obj)}"
        for pred, obj in graph.predicate_objects(term)
    ]
    return "\n".join(sorted(lines))


def changed_terms_since_approved(current: Graph, root: Path | None = None) -> set[URIRef]:
    """Class IRIs whose triples differ from the last approved release."""
    root = root or _repo_root()
    rev = approved_baseline_rev(root)
    if not rev:
        return set()
    try:
        baseline = _load_ttl_graph(rev, root)
    except Exception as exc:
        log.warning("Could not load vocabulary at %s: %s", rev, exc)
        return set()

    changed: set[URIRef] = set()
    for term in set(current.subjects(RDF.type, OWL.Class)):
        if not isinstance(term, URIRef):
            continue
        if _term_signature(current, term) != _term_signature(baseline, term):
            changed.add(term)
    log.info(
        "Marked %d terms as draft relative to %s",
        len(changed),
        rev[:12],
    )
    return changed
