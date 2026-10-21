from typer.testing import CliRunner

from toolbox.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "toolbox" in result.output


def test_qr_writes_png(tmp_path):
    output = tmp_path / "code.png"
    result = runner.invoke(app, ["qr", "https://example.com", "-o", str(output)])
    assert result.exit_code == 0, result.output
    assert output.read_bytes().startswith(b"\x89PNG")


def test_qr_format_follows_extension(tmp_path):
    output = tmp_path / "code.svg"
    result = runner.invoke(app, ["qr", "hello", "-o", str(output)])
    assert result.exit_code == 0, result.output
    assert "<svg" in output.read_text()


def test_qr_reads_stdin(tmp_path):
    output = tmp_path / "code.png"
    result = runner.invoke(app, ["qr", "-", "-o", str(output)], input="from stdin\n")
    assert result.exit_code == 0, result.output
    assert output.exists()


def test_qr_prints_to_terminal_without_output():
    result = runner.invoke(app, ["qr", "hello"])
    assert result.exit_code == 0
    assert "█" in result.output


def test_qr_rejects_unknown_extension(tmp_path):
    result = runner.invoke(app, ["qr", "hello", "-o", str(tmp_path / "code.jpg")])
    assert result.exit_code == 2


def test_qr_reports_invalid_color(tmp_path):
    result = runner.invoke(
        app, ["qr", "hello", "-o", str(tmp_path / "a.png"), "--fg", "nope"]
    )
    assert result.exit_code == 1
    assert "invalid color" in result.output
