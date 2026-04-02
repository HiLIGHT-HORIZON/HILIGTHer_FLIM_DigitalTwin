# Sensitive Materials Remediation

This repository previously tracked files under `resources/` that should not be published.

## Local containment completed

- `resources/` is now ignored by git, except for `resources/.gitkeep`.
- Tracked files under `resources/` should be removed from the index with:

```powershell
git rm --cached -r resources
git add .gitignore resources/.gitkeep
git commit -m "chore: stop tracking sensitive resources"
```

This keeps the local files on disk while removing them from future commits.

## History rewrite still required

Removing the files from the latest commit is not enough because the files already exist in published history.

Preferred approach with `git filter-repo`:

```powershell
git filter-repo --invert-paths --path resources --force
```

If `git filter-repo` is not installed:

```powershell
python -m pip install git-filter-repo
```

If only specific files need purging instead of the whole folder:

```powershell
git filter-repo --invert-paths `
  --path resources/D6.1_HILIGHT_M18_SEN_v2.docx `
  --path resources/FisherCompression.docx `
  --path resources/6f156561-1530-413d-80d6-218f90a6cfd4 `
  --force
```

After rewriting history:

```powershell
git push origin --force --all
git push origin --force --tags
```

## Follow-up actions

1. Treat any published credentials, tokens, or private data as compromised and rotate them.
2. Ask collaborators to re-clone or hard-reset to the rewritten history.
3. Check GitHub releases, pull request attachments, cached artifacts, and Actions logs for copies of the same files.
4. If the data is highly sensitive, open a GitHub support request to help purge cached copies.
