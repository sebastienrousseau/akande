# Homebrew distribution

The `akande.rb` formula in this directory is the *source of truth*
for the published tap.  Each release the file is copied
(or PR'd via `brew bump-formula-pr`) into the tap repository at
`github.com/sebastienrousseau/homebrew-akande`.

## Bootstrapping the tap (one-off)

```bash
gh repo create sebastienrousseau/homebrew-akande --public
cd ../homebrew-akande
mkdir -p Formula
cp ../akande/homebrew/akande.rb Formula/akande.rb
git add Formula/akande.rb
git commit -m "Initial akande formula"
git push
```

## Cutting a release

1. Tag a v0.0.6 (or later) release on this repo and let CI publish
   the sdist to PyPI.
2. From inside the tap clone:
   ```bash
   brew bump-formula-pr Formula/akande.rb \
       --url=https://files.pythonhosted.org/packages/source/a/akande/akande-0.0.6.tar.gz
   ```
   This computes the new SHA256 and opens a PR.
3. Merge the PR.  Users get the new release on their next
   `brew update && brew upgrade akande`.

## User-facing install

```bash
brew tap sebastienrousseau/akande
brew install akande
akande --help
```
