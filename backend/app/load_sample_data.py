"""
Load CSV files from backend/data into Neo4j.

Usage:
  python -m app.load_sample_data
"""

import os

from app.data_loader import DataLoader
from app.graph_constructor import GraphConstructor
from app.load_sap_o2c_data import main as _sap_main  # noqa: F401


def main():
  # Prefer the SAP dataset if present.
  sap_dir = os.getenv("SAP_DATA_DIR")
  if not sap_dir:
    # workspace layout: backend/app/<this file> => ../../sap-order-to-cash-dataset
    sap_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sap-order-to-cash-dataset"))

  if sap_dir and os.path.isdir(sap_dir) and os.path.isdir(os.path.join(sap_dir, "sap-o2c-data")):
    # Delegate to SAP loader (uses NEO4J_* env vars).
    from app.load_sap_o2c_data import main as sap_main

    sap_main()
    return

  data_dir = os.getenv("DATA_DIR", "./data")
  uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
  user = os.getenv("NEO4J_USER", "neo4j")
  password = os.getenv("NEO4J_PASSWORD", "password123")
  database = os.getenv("NEO4J_DATABASE", "neo4j")

  loader = DataLoader(data_dir)
  constructor = GraphConstructor(uri, user, password, database=database)

  try:
    file_mapping = {
      "Order": "orders.csv",
      "OrderItem": "order_items.csv",
      "Invoice": "invoices.csv",
      "Delivery": "deliveries.csv",
      "Payment": "payments.csv",
      "Customer": "customers.csv",
      "Product": "products.csv",
    }

    data = loader.load_csv_files(file_mapping)
    constructor.initialize_schema()

    for entity_type, df in data.items():
      records = loader.normalize_entity(df, entity_type)
      constructor.create_nodes_batch(entity_type, records)

    orders_df = data.get("Order")
    order_items_df = data.get("OrderItem")
    invoices_df = data.get("Invoice")
    deliveries_df = data.get("Delivery")
    payments_df = data.get("Payment")

    if orders_df is not None:
      constructor.create_relationships_batch(
        "Customer",
        "customer_id",
        loader.extract_relationships(orders_df, "Order", "customer_id", "order_id"),
        "Order",
        "order_id",
        "PLACES",
      )

    if order_items_df is not None:
      constructor.create_relationships_batch(
        "Order",
        "order_id",
        loader.extract_relationships(order_items_df, "OrderItem", "order_id", "order_item_id"),
        "OrderItem",
        "order_item_id",
        "CONTAINS",
      )
      constructor.create_relationships_batch(
        "OrderItem",
        "order_item_id",
        loader.extract_relationships(order_items_df, "OrderItem", "order_item_id", "product_id"),
        "Product",
        "product_id",
        "REFERS_TO",
      )

    if deliveries_df is not None:
      constructor.create_relationships_batch(
        "Order",
        "order_id",
        loader.extract_relationships(deliveries_df, "Delivery", "order_id", "delivery_id"),
        "Delivery",
        "delivery_id",
        "SHIPPED_BY",
      )

    if invoices_df is not None:
      constructor.create_relationships_batch(
        "Order",
        "order_id",
        loader.extract_relationships(invoices_df, "Invoice", "order_id", "invoice_id"),
        "Invoice",
        "invoice_id",
        "GENERATES",
      )

    if payments_df is not None:
      constructor.create_relationships_batch(
        "Invoice",
        "invoice_id",
        loader.extract_relationships(payments_df, "Payment", "invoice_id", "payment_id"),
        "Payment",
        "payment_id",
        "RECEIVES",
      )

    print("Sample data load complete.")
  finally:
    constructor.close()


if __name__ == "__main__":
  main()
