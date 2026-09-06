"""Unit tests for LedgerGuard storage and service interfaces."""

import pytest

from app.services.dynamodb import DynamoDBInvoiceRepository
from app.services.interfaces import DocumentStore, InvoiceRepository, JobQueue, SecretProvider
from app.services.s3 import S3DocumentStore
from app.services.secrets import SecretsManagerProvider
from app.services.sqs import SQSJobQueue


def test_interfaces_cannot_be_instantiated_directly():
    """Abstract base classes must raise TypeError when instantiated directly."""
    with pytest.raises(TypeError):
        DocumentStore()  # type: ignore

    with pytest.raises(TypeError):
        InvoiceRepository()  # type: ignore

    with pytest.raises(TypeError):
        JobQueue()  # type: ignore

    with pytest.raises(TypeError):
        SecretProvider()  # type: ignore


def test_implementations_subclass_interfaces():
    """Concrete service implementations must inherit from their respective ABCs."""
    assert issubclass(S3DocumentStore, DocumentStore)
    assert issubclass(DynamoDBInvoiceRepository, InvoiceRepository)
    assert issubclass(SQSJobQueue, JobQueue)
    assert issubclass(SecretsManagerProvider, SecretProvider)
