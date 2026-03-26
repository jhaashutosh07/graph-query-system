import os

import pandas as pd

from app.data_loader import DataLoader


def test_normalize_entity_order_item_id_column():
    root = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(root, "data")

    loader = DataLoader(data_dir=data_dir)
    df = pd.read_csv(os.path.join(data_dir, "order_items.csv"))

    normalized = loader.normalize_entity(df, "OrderItem")
    assert isinstance(normalized, list)
    assert len(normalized) > 0

    # Must match GraphConstructor.ENTITY_SCHEMA unique_property for OrderItem
    assert "order_item_id" in normalized[0]


def test_validate_data_does_not_crash_on_order_item():
    root = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(root, "data")

    loader = DataLoader(data_dir=data_dir)
    loader.load_csv_files(
        {
            "Order": "orders.csv",
            "OrderItem": "order_items.csv",
        }
    )
    report = loader.validate_data()
    assert "stats" in report
    assert report["stats"]["Order"] > 0
    assert report["stats"]["OrderItem"] > 0

