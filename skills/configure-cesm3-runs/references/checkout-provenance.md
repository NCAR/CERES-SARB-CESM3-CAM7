# CESM Checkout Provenance

Use checkout snapshots to accelerate discovery and detect drift. They are indexes, not frozen
copies of CESM documentation and not substitutes for the live source tree.

## Authority order

1. The selected live CESM checkout and its component working trees.
2. CIME query output and the resolved XML, namelists, and `CaseDocs` of the specific case.
3. A versioned, generated checkout reference whose check mode passes.
4. Historical project documentation and remembered aliases.

If these disagree, report the difference and follow the higher-authority source. In particular,
infer CAM physics from the expanded atmosphere token, not from an alias name.

## Audit procedure

1. Resolve the CESM root and record its full commit, describe/tag, branch or detached state, and
   short status.
2. Inspect top-level git-fleximod components and relevant nested science repositories. Record full
   commits and expected tags. Treat a present directory as a component only when it is the root of
   a Git working tree.
3. Separate the immutable upstream baseline from the deployed local overlay. A dirty component is
   not automatically an error: list tracked and untracked paths and use a content fingerprint when
   the project supplies one.
4. Query CIME live for candidate compsets, grids, machine/compiler/MPI choices, and support
   declarations. Inspect the atmosphere token in every expanded compset.
5. Read relevant RST, Markdown, XML, and source files directly from the checkout. Conversion to
   Markdown is unnecessary. For CAM options, prefer namelist definitions/defaults and use-case
   fragments over prose summaries.
6. After creating or inspecting a case, verify `xmlquery`, `preview_namelists`, `preview_run`, and
   generated `CaseDocs`. Record both the requested alias and resolved long name.

## Versioned reference workflow

When a project contains `scripts/update_cesm3_reference.py`, use:

```bash
python scripts/update_cesm3_reference.py --check
python scripts/update_cesm3_reference.py
python scripts/update_cesm3_reference.py --check
```

Run check mode first. If it reports drift during a read-only status task, use live sources and
report that the snapshot is stale; do not mutate the repository. If the user requested provenance
maintenance, regenerate it, review semantic changes, validate it, and commit the generator and
generated Markdown together.

Review compset atmosphere tokens, support declarations, component tags/commits, dirty-path lists,
overlay fingerprints, machine resources, and namelist defaults rather than accepting a large
mechanical diff blindly.

Regenerate after changing the CESM tag, component revisions, CIME configuration metadata, machine
configuration, or deployed project overlay. A content-based overlay fingerprint ensures a source
edit is detected even when the set of dirty paths remains unchanged.
