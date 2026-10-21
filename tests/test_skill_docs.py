"""The toolbox-pixel skill documents every command; keep it in step with the CLI."""

import re
from pathlib import Path

import pytest
import typer
from typer.core import TyperCommand, TyperGroup, TyperOption

from toolbox.cli import app

SKILL = Path(__file__).parent.parent / "skills" / "toolbox-pixel"
SHARED_OPTIONS = {"-a", "-f", "-l"}  # documented once for every drawing command


def pixel_commands() -> dict[str, TyperCommand]:
    """Every ``toolbox pixel`` command by name, e.g. ``rect`` or ``frame add``."""
    pixel = typer.main.get_command(app).commands["pixel"]
    commands = {}
    for name, command in pixel.commands.items():
        if isinstance(command, TyperGroup):
            for sub, subcommand in command.commands.items():
                commands[f"{name} {sub}"] = subcommand
        else:
            commands[name] = command
    return commands


def option_names(command: TyperCommand) -> set[str]:
    return {
        name
        for param in command.params
        if isinstance(param, TyperOption)
        for name in [*param.opts, *param.secondary_opts]
    }


def reference_rows() -> list[tuple[str, str]]:
    """(command, rest of the row) for each row of reference.md's command table."""
    text = (SKILL / "reference.md").read_text()
    table = text[text.index("## Commands") : text.index("## Sprite sheets")]
    rows = []
    for line in table.splitlines():
        match = re.match(r"\| `([a-z]+(?: (?:add|remove|rename|duration))?) ", line)
        if match:
            rows.append((match.group(1), line))
    return rows


def test_reference_covers_every_command():
    documented = {name for name, _ in reference_rows()}
    documented.add("layer rename")  # shares a row with `layer remove`
    assert documented == set(pixel_commands())


@pytest.mark.parametrize(("name", "row"), reference_rows())
def test_reference_options_exist(name: str, row: str):
    options = set(re.findall(r"(?<![\w-])--?[a-z][\w-]*", row)) - SHARED_OPTIONS
    assert options <= option_names(pixel_commands()[name])


def test_skill_command_table_options_exist():
    commands = pixel_commands()
    every_option = set().union(*(option_names(c) for c in commands.values()))
    text = (SKILL / "SKILL.md").read_text()
    table = text[text.index("## Commands") : text.index("## More")]
    assert set(re.findall(r"(?<![\w-])--[a-z][\w-]*", table)) <= every_option
