from fraud_platform.config import DataPaths


def test_layers_are_separate(tmp_path):
    paths = DataPaths(tmp_path)
    layers = [paths.raw, paths.bronze, paths.silver, paths.gold, paths.quarantine]
    assert len(set(layers)) == 5
    assert all(path.parent == tmp_path for path in layers)


def test_create_preserves_existing_data(tmp_path):
    paths = DataPaths(tmp_path)
    paths.create()
    source = paths.raw / "example.csv"
    source.write_text("amount\n10\n", encoding="utf-8")
    paths.create()
    assert source.read_text(encoding="utf-8") == "amount\n10\n"
    assert all((tmp_path / layer).is_dir() for layer in
               ("raw", "bronze", "silver", "gold", "quarantine"))
