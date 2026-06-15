from __future__ import annotations


def test_storage_package_lazy_getattr_resolves_symbol() -> None:
    import flock.storage as storage_pkg

    assert storage_pkg.serialize_index(["a", "b"]) == '["a", "b"]'


def test_storage_package_lazy_getattr_missing_symbol() -> None:
    import flock.storage as storage_pkg

    try:
        _ = storage_pkg.DOES_NOT_EXIST
    except AttributeError as err:
        assert "has no attribute" in str(err)
    else:
        raise AssertionError("Expected AttributeError for unknown export")


def test_storage_package_exports_include_expected_symbols() -> None:
    import flock.storage as storage_pkg

    expected = {
        "DaprStateBlackboardConfig",
        "DaprStateBlackboardStore",
        "DaprStateBlackboardStoreClientConfig",
        "SQLiteQueryBuilder",
        "SQLiteSchemaManager",
        "create_dapr_client",
        "deserialize_agent_snapshot",
        "deserialize_artifact",
        "deserialize_consumption_records",
        "deserialize_index",
        "serialize_agent_snapshot",
        "serialize_artifact",
        "serialize_consumption_records",
        "serialize_index",
    }

    assert expected.issubset(set(storage_pkg.__all__))
