# Release process

1. Update `version` in `pyproject.toml` and add a section to `CHANGELOG.md`.
2. Open a pull request. CI (lint, format, tests on Python 3.11 and 3.12, dependency audit) must pass.
3. After the merge, either push a tag (`git tag v1.4.0 && git push origin v1.4.0`) or run the **Release** workflow by hand with the version.
4. The workflow checks that the tag matches `pyproject.toml`, then:
   - builds and pushes the multi-arch image to GHCR with provenance and an SBOM, and signs it with cosign (keyless);
   - builds the wheel and sdist, writes `SHA256SUMS`, and attaches all three to the GitHub Release;
   - publishes the package to PyPI through trusted publishing, behind the `pypi` environment.
5. Check the release page for the three assets, then verify the image:

```bash
cosign verify ghcr.io/gerardrecinto/devops-mcp:1.4.0 \
  --certificate-identity-regexp 'https://github.com/gerardrecinto/devops-mcp/.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

A failed release is fixed with a new patch version, never by moving a tag.
