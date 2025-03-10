"""Check what happens when running on non-existent file/directory."""


from typing import TYPE_CHECKING

from nbqa.__main__ import main

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture


def test_file_not_found(capsys: "CaptureFixture") -> None:
    """Check useful error message is raised if file or directory doesn't exist."""
    msg = "No such file or directory: i_dont_exist.ipynb"

    main(["isort", "i_dont_exist.ipynb", "--profile=black"])
    _, err = capsys.readouterr()
    assert msg in err
