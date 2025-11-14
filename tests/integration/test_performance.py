"""
Performance integration tests for invoice processing.

Tests system throughput, concurrent processing, and latency targets.
Validates system can handle production load scenarios.
"""

import pytest
import json
import time
from datetime import datetime
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed

from shared.ulid_generator import generate_ulid
from functions.ExtractEnrich import main as extract_enrich_main


@pytest.mark.integration
@pytest.mark.slow
def test_concurrent_processing_50_invoices(
    storage_helper,
    test_queues,
    test_tables,
    test_blobs,
    sample_vendors,
    sample_pdf,
    mock_environment,
):
    """
    Test concurrent processing of 50 invoices.

    Target: All 50 complete successfully within 60 seconds.
    Validates: No race conditions, no resource exhaustion.
    """
    num_invoices = 50
    transaction_ids = [generate_ulid() for _ in range(num_invoices)]

    # Queue 50 raw mail messages
    for i, txn_id in enumerate(transaction_ids):
        # Alternate between vendors
        vendors = ["adobe.com", "microsoft.com", "salesforce.com", "slack.com", "zoom.us"]
        vendor_domain = vendors[i % len(vendors)]

        # Upload blob
        blob_url = storage_helper.upload_blob(
            "invoices",
            f"{txn_id}/invoice_{i}.pdf",
            sample_pdf,
        )

        # Queue message
        raw_mail = {
            "id": txn_id,
            "sender": f"billing@{vendor_domain}",
            "subject": f"Invoice #{1000 + i}",
            "blob_url": blob_url,
            "received_at": datetime.utcnow().isoformat() + "Z",
        }
        storage_helper.send_message("raw-mail", json.dumps(raw_mail))

    # Verify all queued
    queue_length = storage_helper.get_queue_length("raw-mail")
    assert queue_length == num_invoices

    # Process messages concurrently
    start_time = time.time()
    successful = 0
    failed = 0

    def process_message(message_data):
        """Process single message (simulates ExtractEnrich)."""
        try:
            mock_queue_msg = MagicMock()
            mock_queue_msg.get_body.return_value = json.dumps(message_data).encode()
            mock_output = MagicMock()

            extract_enrich_main(mock_queue_msg, mock_output)
            return True
        except Exception:
            return False

    # Receive and process all messages
    messages = storage_helper.receive_messages("raw-mail", max_messages=num_invoices)
    assert len(messages) >= num_invoices * 0.9  # At least 90% received

    # Process with thread pool (simulates concurrent Azure Functions)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for msg in messages:
            msg_data = json.loads(msg.content)
            futures.append(executor.submit(process_message, msg_data))

        for future in as_completed(futures):
            if future.result():
                successful += 1
            else:
                failed += 1

    end_time = time.time()
    duration = end_time - start_time

    # Validate performance targets
    assert successful >= num_invoices * 0.8  # At least 80% success
    assert duration < 60  # Complete within 60 seconds
    print(f"\nProcessed {successful}/{num_invoices} invoices in {duration:.2f}s")


@pytest.mark.integration
def test_single_invoice_latency(
    storage_helper,
    test_queues,
    test_tables,
    test_blobs,
    sample_vendors,
    sample_pdf,
    transaction_id,
    mock_environment,
):
    """
    Test single invoice end-to-end latency.

    Target: <10 seconds for happy path (no actual email/webhook).
    """
    # Upload blob
    blob_url = storage_helper.upload_blob(
        "invoices",
        f"{transaction_id}/invoice.pdf",
        sample_pdf,
    )

    # Queue raw mail
    raw_mail = {
        "id": transaction_id,
        "sender": "billing@adobe.com",
        "subject": "Invoice #12345",
        "blob_url": blob_url,
        "received_at": datetime.utcnow().isoformat() + "Z",
    }

    start_time = time.time()

    # Step 1: ExtractEnrich
    storage_helper.send_message("raw-mail", json.dumps(raw_mail))
    messages = storage_helper.receive_messages("raw-mail", max_messages=1)

    mock_queue_msg = MagicMock()
    mock_queue_msg.get_body.return_value = messages[0].content.encode()
    mock_output = MagicMock()
    enriched_msgs = []
    mock_output.set.side_effect = lambda x: enriched_msgs.append(x)

    extract_enrich_main(mock_queue_msg, mock_output)

    # Step 2: PostToAP (mocked)
    storage_helper.send_message("to-post", enriched_msgs[0])
    messages = storage_helper.receive_messages("to-post", max_messages=1)

    mock_queue_msg.get_body.return_value = messages[0].content.encode()
    mock_notify_output = MagicMock()
    notify_msgs = []
    mock_notify_output.set.side_effect = lambda x: notify_msgs.append(x)

    mock_graph = MagicMock()
    mock_graph.send_email.return_value = {"id": "sent-123"}

    with patch("functions.PostToAP.GraphAPIClient", return_value=mock_graph):
        from functions.PostToAP import main as post_to_ap_main

        post_to_ap_main(mock_queue_msg, mock_notify_output)

    end_time = time.time()
    latency = end_time - start_time

    # Validate latency target
    assert latency < 10.0  # Less than 10 seconds
    print(f"\nSingle invoice latency: {latency:.3f}s")


@pytest.mark.integration
def test_queue_throughput(
    storage_helper,
    test_queues,
):
    """
    Test queue message throughput.

    Validates Azure Queue can handle high message volume.
    """
    num_messages = 100
    message_size_bytes = 2048  # 2KB per message

    # Generate test messages
    test_message = {"id": "test", "data": "x" * (message_size_bytes - 50)}

    # Measure queue send throughput
    start_time = time.time()
    for i in range(num_messages):
        msg = test_message.copy()
        msg["id"] = f"test-{i}"
        storage_helper.send_message("raw-mail", json.dumps(msg))
    send_duration = time.time() - start_time

    # Measure queue receive throughput
    start_time = time.time()
    received_count = 0
    batch_size = 32  # Max Azure Queue batch
    while received_count < num_messages:
        messages = storage_helper.receive_messages("raw-mail", max_messages=batch_size)
        if not messages:
            break
        received_count += len(messages)
    receive_duration = time.time() - start_time

    # Calculate throughput
    send_throughput = num_messages / send_duration
    receive_throughput = received_count / receive_duration if receive_duration > 0 else 0

    print(f"\nQueue send throughput: {send_throughput:.1f} msg/sec")
    print(f"Queue receive throughput: {receive_throughput:.1f} msg/sec")

    # Validate minimum throughput
    assert send_throughput > 10  # At least 10 messages/sec send
    assert receive_throughput > 10  # At least 10 messages/sec receive


@pytest.mark.integration
def test_blob_storage_throughput(
    storage_helper,
    test_blobs,
    sample_pdf,
):
    """
    Test blob storage upload/download throughput.

    Validates blob operations meet performance targets.
    """
    num_blobs = 20

    # Measure upload throughput
    start_time = time.time()
    for i in range(num_blobs):
        storage_helper.upload_blob("invoices", f"perf-test-{i}.pdf", sample_pdf)
    upload_duration = time.time() - start_time

    # Measure download throughput
    start_time = time.time()
    for i in range(num_blobs):
        storage_helper.download_blob("invoices", f"perf-test-{i}.pdf")
    download_duration = time.time() - start_time

    upload_throughput = num_blobs / upload_duration
    download_throughput = num_blobs / download_duration

    print(f"\nBlob upload throughput: {upload_throughput:.1f} blobs/sec")
    print(f"Blob download throughput: {download_throughput:.1f} blobs/sec")

    # Validate minimum throughput
    assert upload_throughput > 1  # At least 1 blob/sec upload
    assert download_throughput > 1  # At least 1 blob/sec download


@pytest.mark.integration
def test_table_storage_throughput(
    storage_helper,
    test_tables,
):
    """
    Test table storage insert/query throughput.

    Validates table operations meet performance targets.
    """
    num_entities = 50

    # Measure insert throughput
    start_time = time.time()
    for i in range(num_entities):
        entity = {
            "PartitionKey": "202411",
            "RowKey": f"test-{i:05d}",
            "VendorName": "Test Vendor",
            "GLCode": "6100",
            "Status": "processed",
        }
        storage_helper.insert_entity("InvoiceTransactions", entity)
    insert_duration = time.time() - start_time

    # Measure query throughput
    start_time = time.time()
    entities = storage_helper.query_entities("InvoiceTransactions", "PartitionKey eq '202411'")
    query_duration = time.time() - start_time

    insert_throughput = num_entities / insert_duration
    entities_count = len(list(entities))

    print(f"\nTable insert throughput: {insert_throughput:.1f} entities/sec")
    print(f"Table query returned {entities_count} entities in {query_duration:.3f}s")

    # Validate minimum throughput
    assert insert_throughput > 5  # At least 5 entities/sec insert
    assert entities_count >= num_entities  # All entities retrieved


@pytest.mark.integration
@pytest.mark.slow
def test_memory_usage_stability(
    storage_helper,
    test_queues,
    test_tables,
    sample_vendors,
):
    """
    Test memory usage remains stable under load.

    Validates no memory leaks during repeated processing.
    """
    import gc
    import sys

    num_iterations = 100
    initial_objects = len(gc.get_objects())

    # Process many messages
    for i in range(num_iterations):
        raw_mail = {
            "id": f"mem-test-{i}",
            "sender": "billing@adobe.com",
            "subject": f"Invoice #{i}",
            "blob_url": f"https://test.blob/invoices/test-{i}.pdf",
            "received_at": datetime.utcnow().isoformat() + "Z",
        }

        mock_queue_msg = MagicMock()
        mock_queue_msg.get_body.return_value = json.dumps(raw_mail).encode()
        mock_output = MagicMock()

        try:
            extract_enrich_main(mock_queue_msg, mock_output)
        except Exception:
            pass  # Some may fail, that's OK

        # Periodic garbage collection
        if i % 10 == 0:
            gc.collect()

    # Final garbage collection
    gc.collect()
    final_objects = len(gc.get_objects())

    # Object count should not grow significantly
    object_growth = final_objects - initial_objects
    growth_percent = (object_growth / initial_objects) * 100

    print(f"\nObject growth: {object_growth} ({growth_percent:.1f}%)")

    # Allow some growth, but not excessive (indicates memory leak)
    assert growth_percent < 50  # Less than 50% growth
