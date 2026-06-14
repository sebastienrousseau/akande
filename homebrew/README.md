# `homebrew/` — Àkàndé Homebrew distribution

The `akande.rb` formula in this directory is the **source of truth**
for the published tap. On each release the file is copied (or PR'd
via `brew bump-formula-pr`) into the tap repository at
`github.com/sebastienrousseau/homebrew-akande`.

> Homebrew resolves `brew tap sebastienrousseau/akande` to the
> repository `homebrew-akande` automatically — there is no separate
> short name to memorise.

---

## Bootstrapping the tap (one-off)

```bash
# Create the tap repository.
gh repo create sebastienrousseau/homebrew-akande --public

# Seed it from the main repo's authoritative formula.
cd ../homebrew-akande
mkdir -p Formula
cp ../akande/homebrew/akande.rb Formula/akande.rb
git add Formula/akande.rb
git commit -m "feat: initial akande formula"
git push
```

---

## Cutting a release

1. Tag a `v0.0.6` (or later) release on the main `akande` repository
   and let CI publish the sdist to PyPI.
2. From inside the tap clone, open the formula-bump PR. Replace the
   version in the URL with the release you are cutting:

   ```bash
   brew bump-formula-pr Formula/akande.rb \
       --url=https://files.pythonhosted.org/packages/source/a/akande/akande-0.0.6.tar.gz
   ```

   `brew bump-formula-pr` computes the new SHA-256 and opens the PR.
3. Review and merge the PR. Users get the release on their next
   `brew update && brew upgrade akande`.

---

## User-facing install

```bash
brew tap sebastienrousseau/akande
brew install akande
akande --help
```

## Verifying the formula locally

```bash
brew install --build-from-source ./akande.rb
brew test akande          # runs the formula's `test do` block
brew audit --strict akande
```
