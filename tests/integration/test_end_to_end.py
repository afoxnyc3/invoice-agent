"""
End-to-end integration tests for invoice processing flow.

Tests complete workflows from email ingestion through Teams notification,
validating data consistency across all Azure Storage resources.
"""

import pytest
import json
import time
import base64
from datetime import datetime
from unittest.mock import patch, MagicMock

from MailIngest import main as mail_ingest_main
from ExtractEnrich import main as extract_enrich_main
from PostToAP import main as post_to_ap_main
from Notify import main as notify_main

from shared.models import RawMail, EnrichedInvoice, NotificationMessage
from .utils.assertions import (
    assert_raw_mail_valid,
    assert_enriched_invoice_valid,
    assert_notification_message_valid,
    assert_end_to_end_flow_complete,
)


@pytest.mark.integration
@pytest.mark.e2e
def test_happy_path_known_vendor_flow(
    storage_helper,
    test_queues,
    test_tables,
    test_blobs,
    sample_vendors,
    sample_emails,
    sample_pdf,
    mock_environment,
    mock_teams_webhook,
    transaction_id,
):
    """
    Test complete happy path: email from known vendor flows through all functions.

    Flow: MailIngest → ExtractEnrich → PostToAP → Notify
    Validates: Queue messages, blob storage, table entities, Teams notification
    """
    # STEP 1: Mock Graph API and simulate MailIngest
    mock_graph = MagicMock()
    email = sample_emails["known_vendor"]
    mock_graph.get_unread_emails.return_value = [email]
    mock_graph.get_attachments.return_value = [
        {
            "id": email["attachments"][0]["id"],
            "name": email["attachments"][0]["name"],
            "contentType": "application/pdf",
            "contentBytes": base64.b64encode(sample_pdf).decode(),
            "size": len(sample_pdf),
        }
    ]
    mock_graph.mark_as_read.return_value = True

    # Upload blob to simulate MailIngest output
    blob_url = storage_helper.upload_blob(
        "invoices",
        f"{transaction_id}/invoice_adobe_12345.pdf",
        sample_pdf,
    )

    # Queue RawMail message
    raw_mail = {
        "id": transaction_id,
        "sender": email["sender"]["emailAddress"]["address"],
        "subject": email["subject"],
        "blob_url": blob_url,
        "received_at": email["receivedDateTime"],
    }
    storage_helper.send_message("raw-mail", json.dumps(raw_mail))

    # Validate RawMail message
    messages = storage_helper.receive_messages("raw-mail", max_messages=1)
    assert len(messages) == 1
    raw_mail_obj = assert_raw_mail_valid(messages[0].content)
    assert raw_mail_obj.sender == "billing@adobe.com"

    # STEP 2: Simulate ExtractEnrich
    mock_queue_msg = MagicMock()
    mock_queue_msg.get_body.return_value = messages[0].content.encode()

    mock_output = MagicMock()
    enriched_msgs = []
    mock_output.set.side_effect = lambda x: enriched_msgs.append(x)

    with patch("functions.ExtractEnrich.GraphAPIClient", return_value=mock_graph):
        extract_enrich_main(mock_queue_msg, mock_output)

    # Validate EnrichedInvoice message
    assert len(enriched_msgs) == 1
    enriched_obj = assert_enriched_invoice_valid(enriched_msgs[0])
    assert enriched_obj.vendor_name == "Adobe Inc"
    assert enriched_obj.gl_code == "6100"
    assert enriched_obj.status == "enriched"

    # Queue enriched message
    storage_helper.send_message("to-post", enriched_msgs[0])

    # STEP 3: Simulate PostToAP
    messages = storage_helper.receive_messages("to-post", max_messages=1)
    assert len(messages) == 1

    mock_queue_msg.get_body.return_value = messages[0].content.encode()
    mock_notify_output = MagicMock()
    notify_msgs = []
    mock_notify_output.set.side_effect = lambda x: notify_msgs.append(x)

    with patch("functions.PostToAP.GraphAPIClient", return_value=mock_graph):
        post_to_ap_main(mock_queue_msg, mock_notify_output)

    # Validate NotificationMessage
    assert len(notify_msgs) == 1
    notify_obj = assert_notification_message_valid(notify_msgs[0])
    assert notify_obj.type == "success"
    assert "Adobe Inc" in notify_obj.message

    # Validate InvoiceTransaction logged
    partition_key = datetime.utcnow().strftime("%Y%m")
    transaction = storage_helper.get_entity("InvoiceTransactions", partition_key, transaction_id)
    assert transaction is not None
    assert transaction["VendorName"] == "Adobe Inc"
    assert transaction["GLCode"] == "6100"
    assert transaction["Status"] == "processed"

    # STEP 4: Simulate Notify
    storage_helper.send_message("notify", notify_msgs[0])
    messages = storage_helper.receive_messages("notify", max_messages=1)
    assert len(messages) == 1

    mock_queue_msg.get_body.return_value = messages[0].content.encode()
    notify_main(mock_queue_msg)

    # Validate Teams webhook called
    assert mock_teams_webhook.called
    webhook_call = mock_teams_webhook.call_args
    assert webhook_call[1]["json"]["text"] is not None
    assert webhook_call[1]["json"]["themeColor"] == "00FF00"  # Green for success


@pytest.mark.integration
@pytest.mark.e2e
def test_unknown_vendor_flow(
    storage_helper,
    test_queues,
    test_tables,
    sample_vendors,
    sample_emails,
    sample_pdf,
    mock_environment,
    transaction_id,
):
    """
    Test unknown vendor scenario: vendor not in VendorMaster.

    Expected: Registration email sent to requestor, processing stops.
    """
    # Upload blob for unknown vendor
    blob_url = storage_helper.upload_blob(
        "invoices",
        f"{transaction_id}/invoice_newvendor_99999.pdf",
        sample_pdf,
    )

    # Queue RawMail for unknown vendor
    email = sample_emails["unknown_vendor"]
    raw_mail = {
        "id": transaction_id,
        "sender": email["sender"]["emailAddress"]["address"],
        "subject": email["subject"],
        "blob_url": blob_url,
        "received_at": email["receivedDateTime"],
    }
    storage_helper.send_message("raw-mail", json.dumps(raw_mail))

    # Simulate ExtractEnrich
    messages = storage_helper.receive_messages("raw-mail", max_messages=1)
    mock_queue_msg = MagicMock()
    mock_queue_msg.get_body.return_value = messages[0].content.encode()

    mock_output = MagicMock()
    mock_graph = MagicMock()
    mock_graph.send_email.return_value = {"id": "sent-reg-email"}

    with patch("functions.ExtractEnrich.GraphAPIClient", return_value=mock_graph):
        extract_enrich_main(mock_queue_msg, mock_output)

    # Validate no message queued to to-post (processing stopped)
    mock_output.set.assert_not_called()

    # Validate registration email sent
    assert mock_graph.send_email.called
    email_call = mock_graph.send_email.call_args
    assert email_call[1]["to_address"] == "billing@newvendor.com"
    assert "vendor registration" in email_call[1]["subject"].lower()


@pytest.mark.integration
@pytest.mark.e2e
def test_missing_attachment_flow(
    storage_helper,
    test_queues,
    sample_emails,
    mock_environment,
):
    """
    Test email without attachment: should skip and mark as read.

    Expected: Warning logged, email marked as read, no processing.
    """
    mock_graph = MagicMock()
    email = sample_emails["no_attachment"]
    mock_graph.get_unread_emails.return_value = [email]
    mock_graph.mark_as_read.return_value = True

    mock_timer = MagicMock()
    mock_output = MagicMock()

    with patch("functions.MailIngest.GraphAPIClient", return_value=mock_graph):
        mail_ingest_main(mock_timer, mock_output)

    # Validate email marked as read
    assert mock_graph.mark_as_read.called

    # Validate no message queued
    mock_output.set.assert_not_called()


@pytest.mark.integration
@pytest.mark.e2e
def test_malformed_email_flow(
    storage_helper,
    test_queues,
    sample_emails,
    mock_environment,
):
    """
    Test malformed email (missing required fields).

    Expected: Error handling prevents crash, appropriate logging.
    """
    mock_graph = MagicMock()
    email = sample_emails["malformed"]
    mock_graph.get_unread_emails.return_value = [email]

    mock_timer = MagicMock()
    mock_output = MagicMock()

    # Should raise exception due to missing sender
    with patch("functions.MailIngest.GraphAPIClient", return_value=mock_graph):
        with pytest.raises(Exception):
            mail_ingest_main(mock_timer, mock_output)
