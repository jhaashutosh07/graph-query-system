"""
Ingest the SAP Order-to-Cash dataset (JSONL) into Neo4j.

This loader maps SAP entities to the labels/relationships expected by:
- backend/app/query_engine.py templates (Order/Delivery/Invoice/Payment/Product)
- backend/app/main.py graph exploration endpoints (nodes/edges based on * _id properties)

Mapping (important):
- Sales Order -> :Order (order_id)
- Outbound Delivery -> :Delivery (delivery_id)
- Billing Document -> :Invoice (invoice_id)
- Journal Entry (AR items) -> :Payment (payment_id)
- Material / Product -> :Product (product_id)
- Plant -> :Plant (plant_id) and also :Address (address_id) for compatibility
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from neo4j import GraphDatabase


@dataclass(frozen=True)
class SapPaths:
    sales_order_headers: str
    sales_order_items: str
    outbound_delivery_items: str
    billing_document_headers: str
    billing_document_items: str
    journal_entry_items_accounts_receivable: str
    plants: str
    product_descriptions: str
    business_partners: str


def _iter_jsonl(file_path: str) -> Iterator[Dict[str, Any]]:
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _iter_jsonl_files(folder: str) -> Iterator[str]:
    # We avoid glob here to keep dependencies minimal; use os.walk and filter part-*.jsonl.
    for name in sorted(os.listdir(folder)):
        if name.startswith("part-") and name.endswith(".jsonl"):
            yield os.path.join(folder, name)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _merge_nodes_and_rels(
    driver,
    *,
    order: List[Dict[str, Any]],
    customer: List[Dict[str, Any]],
    product: List[Dict[str, Any]],
    order_item: List[Dict[str, Any]],
    delivery: List[Dict[str, Any]],
    invoice: List[Dict[str, Any]],
    payment: List[Dict[str, Any]],
    plant: List[Dict[str, Any]],
    address: List[Dict[str, Any]],
    relationships: List[Tuple[str, str, str, str, str, str, str, Dict[str, Any]]],
):
    """
    Relationships item:
      (from_label, from_id_prop, from_id, to_label, to_id_prop, to_id, rel_type, rel_props)
    but we pack it to keep signature simple:
      stored as (from_label, from_id_prop, from_id, to_label, rel_type, to_id_prop, to_id, rel_props)
    Here, for simplicity, we store it as:
      (from_label, from_id_prop, from_id, to_label, rel_type, to_id_prop, to_id, rel_props)
    and then unpack internally.
    """

    def _txn(tx):
        # Nodes
        def merge_node(label: str, id_prop: str, items: List[Dict[str, Any]]):
            if not items:
                return
            # id_prop is a fixed identifier like order_id -> safe to embed.
            query = f"""
            UNWIND $items AS item
            MERGE (n:{label} {{{id_prop}: item.{id_prop}}})
            SET n += item
            """
            tx.run(query, items=items)

        merge_node("Order", "order_id", order)
        merge_node("Customer", "customer_id", customer)
        merge_node("Product", "product_id", product)
        merge_node("OrderItem", "order_item_id", order_item)
        merge_node("Delivery", "delivery_id", delivery)
        merge_node("Invoice", "invoice_id", invoice)
        merge_node("Payment", "payment_id", payment)
        merge_node("Plant", "plant_id", plant)
        merge_node("Address", "address_id", address)

        # Relationships
        if not relationships:
            return

        # Group by (from_label, from_id_prop, to_label, to_id_prop, rel_type)
        grouped: Dict[
            Tuple[str, str, str, str, str],
            List[Tuple[str, str, Dict[str, Any]]],
        ] = defaultdict(list)
        for (
            from_label,
            from_id_prop,
            from_id,
            to_label,
            rel_type,
            to_id_prop,
            to_id,
            rel_props,
        ) in relationships:
            grouped[(from_label, from_id_prop, to_label, to_id_prop, rel_type)].append(
                (from_id, to_id, rel_props or {})
            )

        # Create relationships with proper Cypher relationship type.
        for (from_label, from_id_prop, to_label, to_id_prop, rel_type), rel_list in grouped.items():
            # rel_type is embedded; only use fixed values produced by this loader.
            query = f"""
            UNWIND $rels AS r
            MATCH (a:{from_label} {{{from_id_prop}: r.from_id}})
            MATCH (b:{to_label} {{{to_id_prop}: r.to_id}})
            MERGE (a)-[rel:`{rel_type}`]->(b)
            SET rel += r.rel_props
            """
            tx.run(
                query,
                rels=[
                    {"from_id": f_id, "to_id": t_id, "rel_props": props}
                    for (f_id, t_id, props) in rel_list
                ],
            )

    with driver.session() as session:
        session.execute_write(_txn)


def load_sap_o2c_data(driver, sap_root: str) -> None:
    """
    Load SAP JSONL files in sap_root (must contain sap-o2c-data/*).
    """
    sap_root = sap_root.rstrip("/\\")
    if os.path.basename(sap_root).lower() != "sap-o2c-data":
        sap_root = os.path.join(sap_root, "sap-o2c-data")

    paths = SapPaths(
        sales_order_headers=os.path.join(sap_root, "sales_order_headers"),
        sales_order_items=os.path.join(sap_root, "sales_order_items"),
        outbound_delivery_items=os.path.join(sap_root, "outbound_delivery_items"),
        billing_document_headers=os.path.join(sap_root, "billing_document_headers"),
        billing_document_items=os.path.join(sap_root, "billing_document_items"),
        journal_entry_items_accounts_receivable=os.path.join(
            sap_root, "journal_entry_items_accounts_receivable"
        ),
        plants=os.path.join(sap_root, "plants"),
        product_descriptions=os.path.join(sap_root, "product_descriptions"),
        business_partners=os.path.join(sap_root, "business_partners"),
    )

    # Preload plant->address and product_id->name
    plant_to_address: Dict[str, str] = {}
    plant_to_name: Dict[str, str] = {}
    for folder_file in _iter_jsonl_files(paths.plants):
        for rec in _iter_jsonl(folder_file):
            plant_id = _safe_str(rec.get("plant"))
            address_id = _safe_str(rec.get("addressId"))
            if plant_id:
                plant_to_address[plant_id] = address_id
                plant_to_name[plant_id] = _safe_str(rec.get("plantName") or plant_id)

    product_to_name: Dict[str, str] = {}
    for folder_file in _iter_jsonl_files(paths.product_descriptions):
        for rec in _iter_jsonl(folder_file):
            if _safe_str(rec.get("language")).upper() != "EN":
                continue
            product_id = _safe_str(rec.get("product"))
            if product_id:
                product_to_name[product_id] = _safe_str(rec.get("productDescription") or product_id)

    orders: List[Dict[str, Any]] = []
    customers: List[Dict[str, Any]] = []
    products: List[Dict[str, Any]] = []
    order_items: List[Dict[str, Any]] = []
    deliveries: List[Dict[str, Any]] = []
    invoices: List[Dict[str, Any]] = []
    payments: List[Dict[str, Any]] = []
    plants: List[Dict[str, Any]] = []
    addresses: List[Dict[str, Any]] = []

    relationships: List[Tuple[str, str, str, str, str, str, str, Dict[str, Any]]] = []

    # Customer nodes (business partners)
    seen_customer: set[str] = set()
    for folder_file in _iter_jsonl_files(paths.business_partners):
        for rec in _iter_jsonl(folder_file):
            cust_id = _safe_str(rec.get("customer") or rec.get("businessPartner"))
            if not cust_id or cust_id in seen_customer:
                continue
            seen_customer.add(cust_id)
            customers.append(
                {
                    "customer_id": cust_id,
                    "customer_name": _safe_str(rec.get("businessPartnerName") or rec.get("businessPartnerFullName")),
                    "name": _safe_str(rec.get("businessPartnerName") or cust_id),
                }
            )

    # Order nodes
    seen_order: set[str] = set()
    order_to_customer: Dict[str, str] = {}
    for folder_file in _iter_jsonl_files(paths.sales_order_headers):
        for rec in _iter_jsonl(folder_file):
            order_id = _safe_str(rec.get("salesOrder"))
            if not order_id or order_id in seen_order:
                continue
            seen_order.add(order_id)
            customer_id = _safe_str(rec.get("soldToParty"))
            order_to_customer[order_id] = customer_id
            orders.append(
                {
                    "order_id": order_id,
                    "order_date": _safe_str(rec.get("creationDate")),
                    "status": _safe_str(rec.get("overallDeliveryStatus") or rec.get("overallOrdReltdBillgStatus")),
                    "name": order_id,
                    "customer_id": customer_id,
                }
            )

    # Delivery nodes + relationship Order SHIPPED_BY Delivery and Delivery TO_PLANT
    seen_delivery: set[str] = set()
    seen_plant: set[str] = set()
    for folder_file in _iter_jsonl_files(paths.outbound_delivery_items):
        for rec in _iter_jsonl(folder_file):
            delivery_id = _safe_str(rec.get("deliveryDocument"))
            order_id = _safe_str(rec.get("referenceSdDocument"))
            plant_id = _safe_str(rec.get("plant"))
            if not delivery_id or not order_id:
                continue

            if delivery_id not in seen_delivery:
                seen_delivery.add(delivery_id)
                deliveries.append(
                    {
                        "delivery_id": delivery_id,
                        "name": delivery_id,
                        # we might not have a clean date here; keep what exists
                        "ship_date": _safe_str(rec.get("lastChangeDateTime") or rec.get("creationDate") or ""),
                    }
                )

            if plant_id and plant_id not in seen_plant:
                seen_plant.add(plant_id)
                plants.append(
                    {
                        "plant_id": plant_id,
                        "plant_name": plant_to_name.get(plant_id, plant_id),
                        "name": plant_to_name.get(plant_id, plant_id),
                    }
                )

            relationships.append(
                ("Order", "order_id", order_id, "Delivery", "SHIPPED_BY", "delivery_id", delivery_id, {})
            )

            if plant_id:
                relationships.append(
                    (
                        "Delivery",
                        "delivery_id",
                        delivery_id,
                        "Plant",
                        "TO_PLANT",
                        "plant_id",
                        plant_id,
                        {},
                    )
                )

            # Also connect delivery to Address via plant's addressId (if known)
            if plant_id and plant_id in plant_to_address and plant_to_address[plant_id]:
                addr_id = plant_to_address[plant_id]
                relationships.append(
                    (
                        "Delivery",
                        "delivery_id",
                        delivery_id,
                        "Address",
                        "TO_ADDRESS",
                        "address_id",
                        addr_id,
                        {},
                    )
                )
                # Address node
                if not any(a.get("address_id") == addr_id for a in addresses):
                    addresses.append(
                        {"address_id": addr_id, "name": f"PlantAddress:{addr_id}", "address": addr_id}
                    )

    # Invoice nodes and relationship Order GENERATES Invoice
    seen_invoice: set[str] = set()
    for folder_file in _iter_jsonl_files(paths.billing_document_headers):
        for rec in _iter_jsonl(folder_file):
            invoice_id = _safe_str(rec.get("billingDocument"))
            if not invoice_id or invoice_id in seen_invoice:
                continue
            seen_invoice.add(invoice_id)
            invoices.append(
                {
                    "invoice_id": invoice_id,
                    "invoice_date": _safe_str(rec.get("billingDocumentDate")),
                    "status": _safe_str(
                        "cancelled" if rec.get("billingDocumentIsCancelled") in (True, "true", "1") else "active"
                    ),
                    "name": invoice_id,
                    "sold_to_party": _safe_str(rec.get("soldToParty")),
                }
            )

    # Use billing_document_items to connect Order -> Invoice
    seen_invoice_rel: set[Tuple[str, str]] = set()
    for folder_file in _iter_jsonl_files(paths.billing_document_items):
        for rec in _iter_jsonl(folder_file):
            order_id = _safe_str(rec.get("referenceSdDocument"))
            invoice_id = _safe_str(rec.get("billingDocument"))
            if not order_id or not invoice_id:
                continue
            key = (order_id, invoice_id)
            if key in seen_invoice_rel:
                continue
            seen_invoice_rel.add(key)
            relationships.append(
                ("Order", "order_id", order_id, "Invoice", "GENERATES", "invoice_id", invoice_id, {})
            )

    # Payment nodes + relationship Invoice RECEIVES Payment
    seen_payment: set[str] = set()
    seen_payment_rel: set[Tuple[str, str]] = set()
    for folder_file in _iter_jsonl_files(paths.journal_entry_items_accounts_receivable):
        for rec in _iter_jsonl(folder_file):
            invoice_id = _safe_str(rec.get("referenceDocument"))
            payment_id = _safe_str(rec.get("accountingDocument"))
            if not invoice_id or not payment_id:
                continue
            if payment_id not in seen_payment:
                seen_payment.add(payment_id)
                payments.append(
                    {
                        "payment_id": payment_id,
                        "payment_date": _safe_str(rec.get("postingDate") or rec.get("documentDate")),
                        "amount": _safe_str(rec.get("amountInCompanyCodeCurrency") or rec.get("amountInTransactionCurrency")),
                        "payment_method": _safe_str(rec.get("financialAccountType") or ""),
                        "name": payment_id,
                    }
                )
            key = (invoice_id, payment_id)
            if key not in seen_payment_rel:
                seen_payment_rel.add(key)
                relationships.append(
                    ("Invoice", "invoice_id", invoice_id, "Payment", "RECEIVES", "payment_id", payment_id, {})
                )

    # Order items + products
    seen_order_item: set[str] = set()
    seen_product: set[str] = set()
    for folder_file in _iter_jsonl_files(paths.sales_order_items):
        for rec in _iter_jsonl(folder_file):
            order_id = _safe_str(rec.get("salesOrder"))
            item_no = _safe_str(rec.get("salesOrderItem"))
            product_id = _safe_str(rec.get("material"))
            if not order_id or not item_no:
                continue

            order_item_id = f"{order_id}-{item_no}"
            if order_item_id not in seen_order_item:
                seen_order_item.add(order_item_id)
                order_items.append(
                    {
                        "order_item_id": order_item_id,
                        "order_id": order_id,
                        "product_id": product_id,
                        "quantity": _safe_str(rec.get("requestedQuantity") or ""),
                        "unit_price": _safe_str(rec.get("netAmount") or ""),
                        "name": order_item_id,
                    }
                )
                # Relationships Order CONTAINS / IN -> OrderItem, and OrderItem REFERS_TO Product
                relationships.append(
                    ("Order", "order_id", order_id, "OrderItem", "CONTAINS", "order_item_id", order_item_id, {})
                )
                relationships.append(
                    ("OrderItem", "order_item_id", order_item_id, "Order", "IN", "order_id", order_id, {})
                )
                if product_id:
                    if product_id not in seen_product:
                        seen_product.add(product_id)
                        products.append(
                            {
                                "product_id": product_id,
                                "product_name": product_to_name.get(product_id, product_id),
                                "name": product_to_name.get(product_id, product_id),
                                "category": _safe_str(rec.get("materialGroup") or ""),
                                "price": _safe_str(rec.get("netAmount") or ""),
                            }
                        )
                    relationships.append(
                        ("OrderItem", "order_item_id", order_item_id, "Product", "REFERS_TO", "product_id", product_id, {})
                    )

    # Customer PLACES Order relationships
    seen_places: set[Tuple[str, str]] = set()
    for order_id, cust_id in order_to_customer.items():
        if not cust_id:
            continue
        key = (cust_id, order_id)
        if key in seen_places:
            continue
        seen_places.add(key)
        relationships.append(
            ("Customer", "customer_id", cust_id, "Order", "PLACES", "order_id", order_id, {})
        )

    # Execute write
    _merge_nodes_and_rels(
        driver,
        order=orders,
        customer=customers,
        product=products,
        order_item=order_items,
        delivery=deliveries,
        invoice=invoices,
        payment=payments,
        plant=plants,
        address=addresses,
        relationships=relationships,
    )


def main():
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password123")

    # By default, assume workspace layout:
    # backend/app/<this file> => ../../sap-order-to-cash-dataset/sap-o2c-data
    sap_dir = os.getenv("SAP_DATA_DIR")
    if not sap_dir:
        sap_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sap-order-to-cash-dataset"))

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    try:
        load_sap_o2c_data(driver, sap_dir)
        print("SAP Order-to-Cash ingestion complete.")
    finally:
        driver.close()


if __name__ == "__main__":
    main()

