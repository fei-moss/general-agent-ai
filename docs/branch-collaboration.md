# Branch Collaboration

This file owns branch and worktree handling. `origin/Deploy` is the integration base for DockerHost-facing work; deployment facts remain in `docs/DOCKERHOST_RELEASE_RUNBOOK.md`.

1. Fetch the remote base and create an isolated task worktree without changing another checkout.
2. Keep one task per branch. Preserve unrelated dirty or detached checkouts.
3. Use `make verify-change` while dirty and `make verify-candidate` only when clean review evidence is required.
4. Run full release once on the final production-relevant SHA, or verify reusable evidence when HEAD, tree, engine, profile, compare SHA, and merge base are unchanged.
5. Push or deploy only with separate owner authorization. Deploy only a pushed exact ref through the project runbook; never force-push.

Remove a task worktree only after its branch is integrated or explicitly abandoned, the tree is clean, and no running task uses it. Do not remove the long-lived `.worktrees/Deploy` checkout as task cleanup.
