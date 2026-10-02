def test_package_is_importable() -> None:
    import factttl

    assert factttl.__name__ == "factttl"
