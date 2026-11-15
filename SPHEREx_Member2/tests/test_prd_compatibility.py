import ast
from pathlib import Path


def get_parameters(relative_file, function_name):
    source = Path(relative_file).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return [arg.arg for arg in node.args.args]
    raise AssertionError(f"Function {function_name} not found in {relative_file}")


def test_prd_member2_function_names_and_signatures():
    assert get_parameters("science/inspect_fits.py", "inspect_fits") == ["path"]
    assert get_parameters("science/alignment.py", "reproject_to_reference") == ["input_fits", "ref_wcs", "shape_out"]
    assert get_parameters("science/difference.py", "make_difference") == ["reference", "comparison"]
    assert get_parameters("science/difference.py", "significance_difference") == ["ref", "cmp", "ref_var", "cmp_var"]
