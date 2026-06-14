# Homebrew formula template for Àkàndé.
#
# This file lives in the main repo so the diff is reviewable here, but
# the formula is *published* through a tap repository:
#
#     brew tap sebastienrousseau/akande
#     brew install akande
#
# To cut a new release:
#
#   1. Update `url` and `sha256` to point at the v0.0.6 sdist on PyPI.
#      `brew bump-formula-pr` automates this when the tap is set up.
#   2. Confirm `head` points at the main branch of this repo.
#   3. Open a PR against the tap repo with the bumped formula.
#
# The formula installs into a private venv via the Homebrew `Language::Python::Virtualenv`
# DSL so it never collides with the system Python.

class Akande < Formula
  include Language::Python::Virtualenv

  desc     "Self-hosted, provider-agnostic voice AI assistant"
  homepage "https://akande.co"
  url      "https://files.pythonhosted.org/packages/source/a/akande/akande-0.0.6.tar.gz"
  sha256   "REPLACE_WITH_REAL_SHA256_ON_RELEASE"
  license  "Apache-2.0"
  head     "https://github.com/sebastienrousseau/akande.git", branch: "main"

  depends_on "python@3.12"
  depends_on "portaudio"
  depends_on "ffmpeg"

  def install
    virtualenv_install_with_resources
  end

  test do
    # Trivial smoke check — `akande --help` exits 0 once installed.
    assert_match "akande", shell_output("#{bin}/akande --help")
  end
end
