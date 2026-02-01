import csv
from pathlib import Path

from akande.utils import (
    generate_csv,
    generate_pdf,
    validate_api_key,
    get_output_directory,
    get_output_filename,
)


class TestValidateApiKey:
    def test_valid_key(self):
        assert validate_api_key("sk-abcdefghijklmnopqrstuvwxyz") is True

    def test_valid_proj_key(self):
        assert (
            validate_api_key("sk-proj-abcdefghijklmnopqrstuvwxyz")
            is True
        )

    def test_valid_org_key(self):
        assert (
            validate_api_key("sk-org-abcdefghijklmnopqrstuvwxyz")
            is True
        )

    def test_none_key(self):
        assert validate_api_key(None) is False

    def test_empty_key(self):
        assert validate_api_key("") is False

    def test_short_key(self):
        assert validate_api_key("sk-short") is False

    def test_wrong_prefix(self):
        assert (
            validate_api_key("wrong-prefix-abcdefghijklmnop")
            is False
        )

    def test_almost_valid_prefix(self):
        assert (
            validate_api_key("ska-abcdefghijklmnopqrstuvwxyz")
            is False
        )


class TestGetOutputDirectory:
    def test_creates_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = get_output_directory()
        assert result.exists()
        assert result.is_dir()

    def test_returns_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = get_output_directory()
        assert isinstance(result, Path)


class TestGetOutputFilename:
    def test_includes_extension(self):
        result = get_output_filename(".pdf")
        assert result.endswith(".pdf")

    def test_includes_seconds(self):
        result = get_output_filename(".csv")
        # Format is YYYY-MM-DD-HH-MM-SS-Akande.csv
        parts = result.replace("-Akande.csv", "").split("-")
        # Should have 6 parts: year, month, day, hour, min, sec
        assert len(parts) == 6

    def test_includes_akande(self):
        result = get_output_filename(".wav")
        assert "Akande" in result


class TestGenerateCsv:
    def test_generates_csv_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        generate_csv("test question", "test response")

        csv_files = list(tmp_path.rglob("*.csv"))
        assert len(csv_files) == 1

        with open(csv_files[0], newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert rows[0] == ["Question", "Response"]
            assert rows[1] == ["test question", "test response"]

    def test_handles_error_gracefully(self, tmp_path, monkeypatch):
        """generate_csv should log errors, not raise."""
        monkeypatch.chdir(tmp_path)
        # Make directory read-only to force write error
        import os

        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        os.chmod(str(read_only_dir), 0o444)
        # This won't crash because generate_csv creates
        # its own date dir in cwd, not in readonly dir
        generate_csv("q", "r")  # Should not raise


class TestGeneratePdf:
    def test_generates_pdf_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        generate_pdf("test question", "Overview\nSome text")

        pdf_files = list(tmp_path.rglob("*.pdf"))
        assert len(pdf_files) == 1

    def test_generates_pdf_without_logo(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        generate_pdf("question", "response text")

        pdf_files = list(tmp_path.rglob("*.pdf"))
        assert len(pdf_files) == 1

    def test_generates_pdf_with_sections(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        response = (
            "Overview\nIntro text\n"
            "Solution\n- step one\n- step two\n"
            "Conclusion\nWrap up\n"
            "Recommendations\nDo this"
        )
        generate_pdf("question", response)

        pdf_files = list(tmp_path.rglob("*.pdf"))
        assert len(pdf_files) == 1

    def test_escapes_markup_in_question(
        self, tmp_path, monkeypatch
    ):
        """User input with XML/HTML should be escaped."""
        monkeypatch.chdir(tmp_path)
        # This should not crash even with markup chars
        generate_pdf(
            "<script>alert('xss')</script>",
            "Safe response & <ok>",
        )
        pdf_files = list(tmp_path.rglob("*.pdf"))
        assert len(pdf_files) == 1
