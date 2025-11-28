"""Unit tests for SubscriptionManager timer function."""

from unittest.mock import Mock, patch, MagicMock
import azure.functions as func
import pytest
from SubscriptionManager import main, _get_subscription_record, _save_subscription_record


# Common environment variables for tests
ENV_VARS = {
    "INVOICE_MAILBOX": "invoices@example.com",
    "MAIL_WEBHOOK_URL": "https://func.azurewebsites.net/api/MailWebhook",
    "GRAPH_CLIENT_STATE": "test-client-state-secret",
    "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
}


class TestSubscriptionManager:
    """Test suite for SubscriptionManager function."""

    @patch.dict("os.environ", {**ENV_VARS, "MAIL_WEBHOOK_URL": ""})
    def test_subscription_manager_missing_webhook_url(self):
        """Test ValueError raised when MAIL_WEBHOOK_URL not configured."""
        timer = Mock(spec=func.TimerRequest)
        with pytest.raises(ValueError, match="Missing MAIL_WEBHOOK_URL"):
            main(timer)

    @patch.dict(
        "os.environ",
        {k: v for k, v in ENV_VARS.items() if k != "GRAPH_CLIENT_STATE"},
    )
    def test_subscription_manager_missing_client_state(self):
        """Test ValueError raised when GRAPH_CLIENT_STATE not configured."""
        timer = Mock(spec=func.TimerRequest)
        with pytest.raises(ValueError, match="Missing GRAPH_CLIENT_STATE"):
            main(timer)

    @patch.dict("os.environ", ENV_VARS)
    @patch("SubscriptionManager.TableServiceClient")
    @patch("SubscriptionManager.GraphAPIClient")
    def test_subscription_manager_new_subscription(self, mock_graph_class, mock_table_class):
        """Test new subscription creation when none exists."""
        # Setup mocks
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.create_subscription.return_value = {
            "id": "sub-123",
            "expirationDateTime": "2024-11-17T10:00:00Z",
        }

        mock_table_client = MagicMock()
        mock_table_service = MagicMock()
        mock_table_class.from_connection_string.return_value = mock_table_service
        mock_table_service.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = []  # No existing subscription

        timer = Mock(spec=func.TimerRequest)
        main(timer)

        mock_graph.create_subscription.assert_called_once()
        mock_table_client.upsert_entity.assert_called_once()

    @patch.dict("os.environ", ENV_VARS)
    @patch("SubscriptionManager.TableServiceClient")
    @patch("SubscriptionManager.GraphAPIClient")
    def test_subscription_manager_renewal_success(self, mock_graph_class, mock_table_class):
        """Test successful renewal of existing subscription."""
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.renew_subscription.return_value = {"expirationDateTime": "2024-11-24T10:00:00Z"}

        mock_table_client = MagicMock()
        mock_table_service = MagicMock()
        mock_table_class.from_connection_string.return_value = mock_table_service
        mock_table_service.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = [
            {
                "PartitionKey": "GraphSubscription",
                "RowKey": "sub-existing",
                "SubscriptionId": "sub-existing",
                "IsActive": True,
            }
        ]

        timer = Mock(spec=func.TimerRequest)
        main(timer)

        mock_graph.renew_subscription.assert_called_once_with("sub-existing")
        mock_graph.create_subscription.assert_not_called()
        mock_table_client.update_entity.assert_called_once()

    @patch.dict("os.environ", ENV_VARS)
    @patch("SubscriptionManager.TableServiceClient")
    @patch("SubscriptionManager.GraphAPIClient")
    def test_subscription_manager_renewal_failure_creates_new(self, mock_graph_class, mock_table_class):
        """Test that failed renewal triggers new subscription creation."""
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.renew_subscription.side_effect = Exception("Subscription expired")
        mock_graph.create_subscription.return_value = {
            "id": "sub-new",
            "expirationDateTime": "2024-11-17T10:00:00Z",
        }

        mock_table_client = MagicMock()
        mock_table_service = MagicMock()
        mock_table_class.from_connection_string.return_value = mock_table_service
        mock_table_service.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = [
            {
                "PartitionKey": "GraphSubscription",
                "RowKey": "sub-old",
                "SubscriptionId": "sub-old",
                "IsActive": True,
            }
        ]

        timer = Mock(spec=func.TimerRequest)
        main(timer)

        mock_graph.renew_subscription.assert_called_once()
        mock_graph.create_subscription.assert_called_once()


class TestSubscriptionHelpers:
    """Test suite for helper functions."""

    def test_get_subscription_record_returns_active(self):
        """Test that first active subscription is returned."""
        mock_table_client = MagicMock()
        mock_table_client.query_entities.return_value = [
            {"SubscriptionId": "sub-1", "IsActive": True},
            {"SubscriptionId": "sub-2", "IsActive": True},
        ]

        result = _get_subscription_record(mock_table_client)

        assert result["SubscriptionId"] == "sub-1"
        mock_table_client.query_entities.assert_called_once()

    def test_get_subscription_record_returns_none_when_empty(self):
        """Test that None is returned when no active subscriptions exist."""
        mock_table_client = MagicMock()
        mock_table_client.query_entities.return_value = []

        result = _get_subscription_record(mock_table_client)

        assert result is None

    def test_save_subscription_record_upserts_entity(self):
        """Test that subscription record is saved with correct fields."""
        mock_table_client = MagicMock()

        _save_subscription_record(mock_table_client, "sub-123", "2024-11-17T10:00:00Z")

        mock_table_client.upsert_entity.assert_called_once()
        saved_entity = mock_table_client.upsert_entity.call_args[0][0]
        assert saved_entity["PartitionKey"] == "GraphSubscription"
        assert saved_entity["RowKey"] == "sub-123"
        assert saved_entity["SubscriptionId"] == "sub-123"
        assert saved_entity["ExpirationDateTime"] == "2024-11-17T10:00:00Z"
        assert saved_entity["IsActive"] is True
