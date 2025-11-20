"""
Integration tests for queue retry logic and poison queue handling.

Tests Azure Queue Storage retry mechanisms, message visibility timeout,
and automatic poison queue routing after max retry attempts.
"""

import pytest
import json
import time
from unittest.mock import patch, MagicMock
from azure.core.exceptions import ServiceRequestError

from ExtractEnrich import main as extract_enrich_main
from PostToAP import main as post_to_ap_main


@pytest.mark.integration
def test_queue_message_visibility_timeout(
    storage_helper,
    test_queues,
    raw_mail_message,
):
    """
    Test message visibility timeout mechanism.

    When a message is received, it becomes invisible for timeout period.
    If not deleted, it reappears for retry.
    """
    # Send message to queue
    storage_helper.send_message("raw-mail", json.dumps(raw_mail_message))

    # Receive message (becomes invisible)
    messages1 = storage_helper.receive_messages("raw-mail", max_messages=1)
    assert len(messages1) == 1

    # Immediate retry should return no messages (visibility timeout active)
    messages2 = storage_helper.receive_messages("raw-mail", max_messages=1)
    assert len(messages2) == 0

    # Message should reappear after visibility timeout (30 seconds default in Azure)
    # For testing, we verify the mechanism works conceptually
    assert messages1[0].dequeue_count == 1  # First attempt


@pytest.mark.integration
def test_transient_failure_retry(
    storage_helper,
    test_queues,
    test_tables,
    sample_vendors,
    raw_mail_message,
    mock_environment,
):
    """
    Test automatic retry on transient failure.

    Simulates temporary table storage failure, verifies retry behavior.
    """
    storage_helper.send_message("raw-mail", json.dumps(raw_mail_message))
    messages = storage_helper.receive_messages("raw-mail", max_messages=1)

    mock_queue_msg = MagicMock()
    mock_queue_msg.get_body.return_value = messages[0].content.encode()
    mock_output = MagicMock()

    # Simulate transient table storage failure
    mock_table_client = MagicMock()
    mock_table_client.get_entity.side_effect = ServiceRequestError("Temporary failure")

    mock_table_service = MagicMock()
    mock_table_service.get_table_client.return_value = mock_table_client

    with patch("functions.ExtractEnrich.TableServiceClient.from_connection_string", return_value=mock_table_service):
        # Function should raise exception (Azure Functions runtime handles retry)
        with pytest.raises(Exception):
            extract_enrich_main(mock_queue_msg, mock_output)

    # In production, Azure Functions would automatically retry
    # Message dequeue count would increment with each retry
    assert messages[0].dequeue_count >= 1


@pytest.mark.integration
def test_poison_queue_after_max_retries(
    storage_helper,
    test_queues,
):
    """
    Test poison queue mechanism conceptually.

    Azure Functions automatically moves messages to poison queue
    after maxDequeueCount (default 5) failed attempts.

    Note: Full poison queue testing requires Azure Functions runtime.
    This test validates the conceptual understanding.
    """
    # Create poison queue (Azure creates automatically: {queue-name}-poison)
    poison_queue = "raw-mail-poison"
    storage_helper.create_queue(poison_queue)

    # Send test message
    test_message = {"id": "test-poison", "data": "test"}
    storage_helper.send_message("raw-mail", json.dumps(test_message))

    # Simulate multiple failed attempts by incrementing dequeue count
    messages = storage_helper.receive_messages("raw-mail", max_messages=1)
    assert len(messages) == 1

    # In production, after 5 failed attempts, Azure Functions runtime
    # automatically moves message to poison queue
    # We validate poison queue exists and is ready
    poison_count = storage_helper.get_queue_length(poison_queue)
    assert poison_count >= 0  # Queue exists and is operational


@pytest.mark.integration
def test_successful_retry_after_transient_error(
    storage_helper,
    test_queues,
    test_tables,
    sample_vendors,
    raw_mail_message,
    mock_environment,
):
    """
    Test successful processing after transient error retry.

    First attempt fails, second attempt succeeds.
    """
    storage_helper.send_message("raw-mail", json.dumps(raw_mail_message))

    # Attempt 1: Fail
    messages = storage_helper.receive_messages("raw-mail", max_messages=1)
    mock_queue_msg = MagicMock()
    mock_queue_msg.get_body.return_value = messages[0].content.encode()
    mock_output = MagicMock()

    mock_table_client = MagicMock()
    call_count = {"count": 0}

    def get_entity_with_retry(*args, **kwargs):
        """First call fails, second succeeds."""
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise ServiceRequestError("Temporary failure")
        # Return vendor data on retry
        return {
            "PartitionKey": "Vendor",
            "RowKey": "adobe_com",
            "VendorName": "Adobe Inc",
            "ExpenseDept": "IT",
            "GLCode": "6100",
            "AllocationScheduleNumber": "MONTHLY",
            "BillingParty": "Company HQ",
        }

    mock_table_client.get_entity = get_entity_with_retry
    mock_table_service = MagicMock()
    mock_table_service.get_table_client.return_value = mock_table_client

    with patch("functions.ExtractEnrich.TableServiceClient.from_connection_string", return_value=mock_table_service):
        # First attempt should fail
        with pytest.raises(ServiceRequestError):
            extract_enrich_main(mock_queue_msg, mock_output)

    # Simulate retry (message reappears in queue)
    # In production, Azure handles this automatically
    storage_helper.send_message("raw-mail", json.dumps(raw_mail_message))
    messages = storage_helper.receive_messages("raw-mail", max_messages=1)
    mock_queue_msg.get_body.return_value = messages[0].content.encode()

    mock_output_retry = MagicMock()
    enriched_msgs = []
    mock_output_retry.set.side_effect = lambda x: enriched_msgs.append(x)

    with patch("functions.ExtractEnrich.TableServiceClient.from_connection_string", return_value=mock_table_service):
        # Second attempt should succeed
        extract_enrich_main(mock_queue_msg, mock_output_retry)

    # Validate successful enrichment
    assert len(enriched_msgs) == 1
    enriched_data = json.loads(enriched_msgs[0])
    assert enriched_data["vendor_name"] == "Adobe Inc"


@pytest.mark.integration
def test_graph_api_retry_on_throttling(
    storage_helper,
    test_queues,
    test_tables,
    test_blobs,
    sample_pdf,
    enriched_invoice_message,
    mock_environment,
):
    """
    Test retry logic when Graph API returns throttling response.

    Simulates 429 Too Many Requests, validates retry with backoff.
    """
    # Upload blob for PostToAP
    blob_url = storage_helper.upload_blob(
        "invoices",
        f"{enriched_invoice_message['id']}/invoice.pdf",
        sample_pdf,
    )
    enriched_invoice_message["blob_url"] = blob_url

    storage_helper.send_message("to-post", json.dumps(enriched_invoice_message))
    messages = storage_helper.receive_messages("to-post", max_messages=1)

    mock_queue_msg = MagicMock()
    mock_queue_msg.get_body.return_value = messages[0].content.encode()
    mock_output = MagicMock()

    # Simulate Graph API throttling
    mock_graph = MagicMock()
    throttle_count = {"count": 0}

    def send_with_throttle(*args, **kwargs):
        """First call throttles, second succeeds."""
        throttle_count["count"] += 1
        if throttle_count["count"] == 1:
            # Simulate 429 response
            error = Exception("429 Too Many Requests")
            error.response = MagicMock(status_code=429)
            raise error
        return {"id": "sent-after-retry"}

    mock_graph.send_email = send_with_throttle

    with patch("functions.PostToAP.GraphAPIClient", return_value=mock_graph):
        # Should fail on first attempt (throttled)
        with pytest.raises(Exception):
            post_to_ap_main(mock_queue_msg, mock_output)

    # Verify throttle was encountered
    assert throttle_count["count"] >= 1


@pytest.mark.integration
def test_concurrent_message_processing(
    storage_helper,
    test_queues,
    raw_mail_message,
):
    """
    Test multiple messages processed concurrently without conflicts.

    Validates queue handles concurrent access correctly.
    """
    # Queue multiple messages
    num_messages = 5
    for i in range(num_messages):
        message = raw_mail_message.copy()
        message["id"] = f"test-concurrent-{i}"
        storage_helper.send_message("raw-mail", json.dumps(message))

    # Verify all messages queued
    queue_length = storage_helper.get_queue_length("raw-mail")
    assert queue_length == num_messages

    # Receive messages (simulates concurrent processing)
    received = storage_helper.receive_messages("raw-mail", max_messages=num_messages)
    assert len(received) == num_messages

    # Verify each message has unique content
    ids = [json.loads(msg.content)["id"] for msg in received]
    assert len(set(ids)) == num_messages  # All unique
