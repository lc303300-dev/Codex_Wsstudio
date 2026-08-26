import importlib.util
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "scripts" / "path_utils.py"
spec = importlib.util.spec_from_file_location("path_utils", MODULE)
path_utils = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(path_utils)


def test_literal_work_path_keeps_underscore_and_segments():
    value = r"D:\SE\_Work\\project\image 01.png"
    assert str(path_utils.normalize_windows_path(value)) == r"D:\SE\_Work\project\image 01.png"


def test_json_escaped_and_quoted_path_is_restored():
    value = r'"D:\\SE\\_Work\\\\project\\clip.png"'
    assert path_utils.canonical_path_text(value) == "D:/SE/_Work/project/clip.png"


def test_unc_path_preserves_unc_prefix():
    assert str(path_utils.normalize_windows_path(r"\\server\\share\\_Work\\a.png")) == r"\\server\share\_Work\a.png"
