"""
Unit tests for PaymentTransaction model.
Tests for Task 1.1.4: Create payment_transactions table
Reference: REQ-011 (Payment Reconciliation)
"""
import pytest
from datetime import datetime
import uuid
from unittest.mock import MagicMock, patch


class TestPaymentTransactionModel:
    """Test cases for PaymentTransaction model."""

    def test_payment_transaction_creation(self):
        """Test creating a PaymentTransaction instance with required fields."""
        from database.models import PaymentTransaction
        
        payment_id = str(uuid.uuid4())
        booking_id = str(uuid.uuid4())
        amount = 1500.50
        method = "UPI"
        status = "pending"
        
        transaction = PaymentTransaction(
            payment_id=payment_id,
            booking_id=booking_id,
            amount=amount,
            method=method,
            status=status
        )
        
        assert transaction.payment_id == payment_id
        assert transaction.booking_id == booking_id
        assert transaction.amount == amount
        assert transaction.method == method
        assert transaction.status == status
        assert transaction.provider_reference is None
        assert transaction.utr_number is None

    def test_payment_transaction_with_all_fields(self):
        """Test creating a PaymentTransaction with all fields populated."""
        from database.models import PaymentTransaction
        
        payment_id = str(uuid.uuid4())
        booking_id = str(uuid.uuid4())
        provider_ref = "RAZORPAY_TX_12345"
        utr = "UPI123456789"
        
        transaction = PaymentTransaction(
            payment_id=payment_id,
            booking_id=booking_id,
            amount=2500.00,
            method="CARD",
            status="success",
            provider_reference=provider_ref,
            utr_number=utr
        )
        
        assert transaction.payment_id == payment_id
        assert transaction.booking_id == booking_id
        assert transaction.amount == 2500.00
        assert transaction.method == "CARD"
        assert transaction.status == "success"
        assert transaction.provider_reference == provider_ref
        assert transaction.utr_number == utr

    def test_payment_transaction_default_values(self):
        """Test that default values are defined in the model."""
        from database.models import PaymentTransaction
        
        # Get the column defaults from the mapper
        status_column = PaymentTransaction.__mapper__.columns['status']
        created_at_column = PaymentTransaction.__mapper__.columns['created_at']
        
        # Check that defaults are defined (they are applied on database insert)
        # The default is a ScalarElementColumnDefault object
        assert status_column.default is not None
        assert str(status_column.default.arg) == "pending"
        assert created_at_column.default is not None

    def test_payment_transaction_status_values(self):
        """Test various payment status values."""
        from database.models import PaymentTransaction
        
        valid_statuses = ["pending", "success", "failed", "refunded"]
        
        for status in valid_statuses:
            transaction = PaymentTransaction(
                payment_id=str(uuid.uuid4()),
                amount=100.00,
                method="UPI",
                status=status
            )
            assert transaction.status == status

    def test_payment_transaction_method_values(self):
        """Test various payment method values."""
        from database.models import PaymentTransaction
        
        valid_methods = ["UPI", "CARD", "NET_BANKING", "WALLET", "DEBIT_CARD"]
        
        for method in valid_methods:
            transaction = PaymentTransaction(
                payment_id=str(uuid.uuid4()),
                amount=100.00,
                method=method
            )
            assert transaction.method == method

    def test_payment_transaction_amount_precision(self):
        """Test that amount handles decimal precision correctly."""
        from database.models import PaymentTransaction
        
        test_cases = [
            (100.00, 100.00),
            (99.99, 99.99),
            (0.01, 0.01),
            (1000000.00, 1000000.00),
        ]
        
        for input_amount, expected_amount in test_cases:
            transaction = PaymentTransaction(
                payment_id=str(uuid.uuid4()),
                amount=input_amount,
                method="UPI"
            )
            assert transaction.amount == expected_amount

    def test_payment_transaction_optional_fields(self):
        """Test that optional fields can be None."""
        from database.models import PaymentTransaction
        
        transaction = PaymentTransaction(
            payment_id=str(uuid.uuid4()),
            amount=500.00,
            method="UPI"
        )
        
        assert transaction.booking_id is None
        assert transaction.provider_reference is None
        assert transaction.utr_number is None

    def test_payment_transaction_utr_number_format(self):
        """Test UTR number handling for UPI transactions."""
        from database.models import PaymentTransaction
        
        utr_numbers = [
            "UPI123456789",
            "123456789012",
            "UTR202312345678",
            None
        ]
        
        for utr in utr_numbers:
            transaction = PaymentTransaction(
                payment_id=str(uuid.uuid4()),
                amount=100.00,
                method="UPI",
                utr_number=utr
            )
            assert transaction.utr_number == utr

    def test_payment_transaction_indexes(self):
        """Test that indexes are defined correctly."""
        from database.models import PaymentTransaction
        
        # Check that table args contains the expected indexes
        table_args = PaymentTransaction.__table_args__
        
        # Convert to list of tuples for easier inspection
        indexes = [arg for arg in table_args if hasattr(arg, 'name')]
        index_names = [idx.name for idx in indexes]
        
        assert 'ix_payment_transactions_payment_id' in index_names
        assert 'ix_payment_transactions_booking_id' in index_names
        assert 'ix_payment_transactions_utr_number' in index_names
        assert 'ix_payment_transactions_status' in index_names
        assert 'ix_payment_transactions_created_at' in index_names

    def test_payment_transaction_table_name(self):
        """Test that the table name is correct."""
        from database.models import PaymentTransaction
        
        assert PaymentTransaction.__tablename__ == "payment_transactions"

    def test_payment_transaction_relationship(self):
        """Test that the booking relationship is defined."""
        from database.models import PaymentTransaction
        
        # Check that the relationship exists
        assert hasattr(PaymentTransaction, 'booking')
        
        # The relationship should be a relationship object
        assert PaymentTransaction.booking is not None

    def test_payment_transaction_timestamps(self):
        """Test that timestamp columns are defined in the model."""
        from database.models import PaymentTransaction
        
        # Check that the timestamp columns exist and have defaults defined
        created_at_column = PaymentTransaction.__mapper__.columns['created_at']
        updated_at_column = PaymentTransaction.__mapper__.columns['updated_at']
        
        # The columns should have default values defined (applied on database insert)
        assert created_at_column.default is not None
        assert updated_at_column.default is not None
        # updated_at should have onupdate defined
        assert updated_at_column.onupdate is not None

    def test_payment_transaction_uuid_generation(self):
        """Test that payment_id column has a default generator defined."""
        from database.models import PaymentTransaction
        
        # Check that the payment_id column has a default function defined
        payment_id_column = PaymentTransaction.__mapper__.columns['payment_id']
        
        # The column should have a default function that generates UUIDs
        assert payment_id_column.default is not None
        assert payment_id_column.primary_key == True

    def test_payment_transaction_repr(self):
        """Test the string representation of PaymentTransaction."""
        from database.models import PaymentTransaction
        
        payment_id = str(uuid.uuid4())
        transaction = PaymentTransaction(
            payment_id=payment_id,
            amount=1000.00,
            method="UPI",
            status="pending"
        )
        
        repr_str = repr(transaction)
        # Check that it's a valid object representation
        assert "PaymentTransaction" in repr_str
        assert payment_id in repr_str


class TestPaymentTransactionIntegration:
    """Integration tests for PaymentTransaction with database operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock()
        return session

    def test_add_payment_transaction_to_session(self, mock_session):
        """Test adding a PaymentTransaction to a database session."""
        from database.models import PaymentTransaction
        
        transaction = PaymentTransaction(
            payment_id=str(uuid.uuid4()),
            amount=1500.00,
            method="CARD",
            status="pending"
        )
        
        mock_session.add(transaction)
        mock_session.add.assert_called_once_with(transaction)

    def test_query_payment_transactions_by_payment_id(self, mock_session):
        """Test querying payment transactions by payment_id."""
        from database.models import PaymentTransaction
        
        # This tests the index usage
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        result = mock_session.query(PaymentTransaction).filter(
            PaymentTransaction.payment_id == "test-payment-id"
        ).first()
        
        assert result is None

    def test_query_payment_transactions_by_booking_id(self, mock_session):
        """Test querying payment transactions by booking_id."""
        from database.models import PaymentTransaction
        
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        
        result = mock_session.query(PaymentTransaction).filter(
            PaymentTransaction.booking_id == "test-booking-id"
        ).all()
        
        assert result == []

    def test_query_payment_transactions_by_utr(self, mock_session):
        """Test querying payment transactions by UTR number."""
        from database.models import PaymentTransaction
        
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        result = mock_session.query(PaymentTransaction).filter(
            PaymentTransaction.utr_number == "UPI123456789"
        ).first()
        
        assert result is None


class TestPaymentTransactionReconciliation:
    """Tests for payment reconciliation functionality."""

    def test_reconciliation_by_status(self):
        """Test filtering transactions by status for reconciliation."""
        from database.models import PaymentTransaction
        
        transactions = [
            PaymentTransaction(
                payment_id=str(uuid.uuid4()),
                amount=100.00,
                method="UPI",
                status="pending"
            ),
            PaymentTransaction(
                payment_id=str(uuid.uuid4()),
                amount=200.00,
                method="CARD",
                status="success"
            ),
            PaymentTransaction(
                payment_id=str(uuid.uuid4()),
                amount=300.00,
                method="NET_BANKING",
                status="failed"
            ),
        ]
        
        pending = [t for t in transactions if t.status == "pending"]
        success = [t for t in transactions if t.status == "success"]
        failed = [t for t in transactions if t.status == "failed"]
        
        assert len(pending) == 1
        assert len(success) == 1
        assert len(failed) == 1

    def test_reconciliation_total_amount(self):
        """Test calculating total amount for reconciliation."""
        from database.models import PaymentTransaction
        
        transactions = [
            PaymentTransaction(
                payment_id=str(uuid.uuid4()),
                amount=100.00,
                method="UPI",
                status="success"
            ),
            PaymentTransaction(
                payment_id=str(uuid.uuid4()),
                amount=200.00,
                method="CARD",
                status="success"
            ),
            PaymentTransaction(
                payment_id=str(uuid.uuid4()),
                amount=50.00,
                method="UPI",
                status="failed"
            ),
        ]
        
        total_success = sum(t.amount for t in transactions if t.status == "success")
        total_failed = sum(t.amount for t in transactions if t.status == "failed")
        
        assert total_success == 300.00
        assert total_failed == 50.00

    def test_utr_number_for_upi_reconciliation(self):
        """Test UTR number tracking for UPI reconciliation."""
        from database.models import PaymentTransaction
        
        upi_transaction = PaymentTransaction(
            payment_id=str(uuid.uuid4()),
            amount=500.00,
            method="UPI",
            status="success",
            utr_number="UPI123456789012"
        )
        
        assert upi_transaction.method == "UPI"
        assert upi_transaction.utr_number is not None
        assert "UPI" in upi_transaction.utr_number or upi_transaction.utr_number.isalnum()

    def test_provider_reference_tracking(self):
        """Test provider reference tracking for all payment methods."""
        from database.models import PaymentTransaction
        
        test_cases = [
            ("RAZORPAY_PAY_123", "RAZORPAY"),
            ("PAYTM_TXN_456", "PAYTM"),
            ("CARD_AUTH_789", "CARD"),
            (None, "UPI"),
        ]
        
        for provider_ref, method in test_cases:
            transaction = PaymentTransaction(
                payment_id=str(uuid.uuid4()),
                amount=100.00,
                method=method,
                provider_reference=provider_ref
            )
            assert transaction.provider_reference == provider_ref


if __name__ == "__main__":
    pytest.main([__file__, "-v"])