"""
Replace :code:`source` code cells of original notebook with ones from converted file.

The converted file will have had the third-party tool run against it by now.
"""

import json
import sys
from difflib import unified_diff
from typing import TYPE_CHECKING, Any, Iterator, List, Mapping, MutableMapping, Set

from nbqa.handle_magics import MagicHandler
from nbqa.notebook_info import NotebookInfo
from nbqa.save_source import CODE_SEPARATOR
from nbqa.text import BOLD, GREEN, RED, RESET

if TYPE_CHECKING:
    from pathlib import Path


def _restore_semicolon(
    source: str,
    cell_number: int,
    trailing_semicolons: Set[int],
) -> str:
    """
    Restore the semicolon at the end of the cell.

    Restore the trailing semicolon if the cell originally contained semicolon
    and the third party tool removed it.

    Parameters
    ----------
    source
        Portion of Python file between cell separators.
    cell_number
        Number of current cell.
    trailing_semicolons
        List of cells which originally had trailing semicolons.

    Returns
    -------
    str
        New source with removed semicolon restored.
    """
    rstripped_source = source.rstrip()
    if cell_number in trailing_semicolons and not rstripped_source.endswith(";"):
        source = rstripped_source + ";"

    return source


def _reinstate_magics(
    source: str,
    temporary_lines: List[MagicHandler],
) -> List[str]:
    """
    Put (preprocessed) line magics back in.

    Parameters
    ----------
    source
        Portion of Python file between cell separators.
    temporary_lines
        Mapping from temporary magic substitutions to original ipython magics

    Returns
    -------
    List[str]
        New source that can be saved into Jupyter Notebook.
    """
    for magic_substitution in temporary_lines:
        source = magic_substitution.restore_magic(source)
    # we take [1:] because the first cell is just '\n'
    return "\n{}".format(source.strip("\n")).splitlines(True)[1:]


def _get_new_source(
    code_cell_number: int,
    notebook_info: NotebookInfo,
    pycell: str,
) -> List[str]:
    """
    Get new source to replace original one with.

    Parameters
    ----------
    code_cell_number
        Cell number (we start counting from 1).
    notebook_info
        Information about notebook cells used for processing
    pycell
        Cell from temporary Python script.

    Returns
    -------
    List
        New source for cell.
    """
    source = _restore_semicolon(
        pycell, code_cell_number, notebook_info.trailing_semicolons
    )
    return _reinstate_magics(
        source,
        notebook_info.temporary_lines.get(code_cell_number, []),
    )


def _get_pycells(python_file: "Path") -> Iterator[str]:
    """
    Parse cells from Python file.

    Parameters
    ----------
    python_file
        Temporary Python file notebook was converted to.

    Returns
    -------
    Iterator
        Parsed cells.
    """
    return iter(python_file.read_text().lstrip(CODE_SEPARATOR).split(CODE_SEPARATOR))


def _notebook_code_cells(
    notebook_json: Mapping[str, Any]
) -> Iterator[MutableMapping[str, Any]]:
    """
    Iterate through notebook's code cells.

    Parameters
    ----------
    notebook_json
        json-parsed notebook.

    Yields
    ------
    MutableMapping[str, Any]
        Cell content.
    """
    for cell in notebook_json["cells"]:
        if cell["cell_type"] == "code":
            yield cell


def mutate(python_file: "Path", notebook: "Path", notebook_info: NotebookInfo) -> None:
    """
    Replace :code:`source` code cells of original notebook.

    Parameters
    ----------
    python_file
        Temporary Python file notebook was converted to.
    notebook
        Jupyter Notebook third-party tool is run against (unmodified).
    notebook_info
        Information about notebook cells used for processing
    """
    notebook_json = json.loads(notebook.read_text(encoding="utf-8"))

    pycells = _get_pycells(python_file)
    for code_cell_number, cell in enumerate(
        _notebook_code_cells(notebook_json), start=1
    ):
        if code_cell_number in notebook_info.code_cells_to_ignore:
            continue
        cell["source"] = _get_new_source(code_cell_number, notebook_info, next(pycells))

    notebook.write_text(
        f"{json.dumps(notebook_json, indent=1, ensure_ascii=False)}\n", encoding="utf-8"
    )


def _print_diff(code_cell_number: int, cell_diff: Iterator[str]) -> None:
    """
    Print diff between cells, colouring as appropriate.

    Parameters
    ----------
    code_cell_number
        Current cell number
    cell_diff
        Diff between original and new versions of cell.
    """
    line_changes = []
    for line in cell_diff:
        if line.startswith("+++") or line.startswith("---"):
            line_changes.append(line)
        elif line.startswith("+"):
            line_changes.append(f"{GREEN}{line}{RESET}")
        elif line.startswith("-"):
            line_changes.append(f"{RED}{line}{RESET}")
        else:
            line_changes.append(line)

    if line_changes:
        header = f"Cell {code_cell_number}"
        headers = [f"{BOLD}{header}{RESET}\n", f"{'-'*len(header)}\n"]
        sys.stdout.writelines(headers + line_changes + ["\n"])


def diff(python_file: "Path", notebook: "Path", notebook_info: NotebookInfo) -> None:
    """
    View diff between new source of code cells and original sources.

    Parameters
    ----------
    python_file
        Temporary Python file notebook was converted to.
    notebook
        Jupyter Notebook third-party tool is run against (unmodified).
    notebook_info
        Information about notebook cells used for processing
    """
    notebook_json = json.loads(notebook.read_text(encoding="utf-8"))

    pycells = _get_pycells(python_file)

    for code_cell_number, cell in enumerate(
        _notebook_code_cells(notebook_json), start=1
    ):
        if code_cell_number in notebook_info.code_cells_to_ignore:
            continue
        new_source = _get_new_source(code_cell_number, notebook_info, next(pycells))
        if cell["source"]:
            cell["source"][-1] += "\n"
        if new_source:
            new_source[-1] += "\n"
        cell_diff = unified_diff(
            cell["source"],
            new_source,
            fromfile=str(notebook),
            tofile=str(notebook),
        )
        _print_diff(code_cell_number, cell_diff)
