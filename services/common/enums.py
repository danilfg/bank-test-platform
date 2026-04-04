from enum import Enum


class SystemRole(str, Enum):
    ADMIN = "ADMIN"
    STUDENT = "STUDENT"


class BusinessRole(str, Enum):
    CLIENT = "CLIENT"
    EMPLOYEE = "EMPLOYEE"


class ClientStatus(str, Enum):
    NEW = "NEW"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    BLOCKED = "BLOCKED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class AccountStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ACTIVE = "ACTIVE"
    PARTIALLY_RESTRICTED = "PARTIALLY_RESTRICTED"
    BLOCKED = "BLOCKED"
    CLOSED = "CLOSED"


class CardStatus(str, Enum):
    ORDERED = "ORDERED"
    PERSONALIZED = "PERSONALIZED"
    ISSUED = "ISSUED"
    ACTIVE = "ACTIVE"
    TEMP_BLOCKED = "TEMP_BLOCKED"
    BLOCKED = "BLOCKED"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"


class TransferStatus(str, Enum):
    DRAFT = "DRAFT"
    CREATED = "CREATED"
    PENDING_ANTI_FRAUD = "PENDING_ANTI_FRAUD"
    PENDING_EXECUTION = "PENDING_EXECUTION"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REVERSED = "REVERSED"


class TicketStatus(str, Enum):
    NEW = "NEW"
    IN_REVIEW = "IN_REVIEW"
    WAITING_FOR_CLIENT = "WAITING_FOR_CLIENT"
    WAITING_FOR_EMPLOYEE = "WAITING_FOR_EMPLOYEE"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class AccountType(str, Enum):
    CURRENT = "CURRENT"
    SAVINGS = "SAVINGS"
    CARD_ACCOUNT = "CARD_ACCOUNT"
    DEPOSIT_SIMULATED = "DEPOSIT_SIMULATED"


class Currency(str, Enum):
    RUB = "RUB"
    EUR = "EUR"
    USD = "USD"


class CardType(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class CardNetwork(str, Enum):
    MIR = "MIR"
    VISA = "VISA"
    MASTERCARD = "MASTERCARD"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TransferType(str, Enum):
    INTERNAL = "INTERNAL"
    SELF = "SELF"
    TOP_UP = "TOP_UP"
    EMPLOYEE_INITIATED = "EMPLOYEE_INITIATED"
    REVERSAL = "REVERSAL"


class TicketCategory(str, Enum):
    CARD = "CARD"
    ACCOUNT = "ACCOUNT"
    TRANSFER = "TRANSFER"
    COMPLAINT = "COMPLAINT"
    TECHNICAL = "TECHNICAL"
    OTHER = "OTHER"


class TicketPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IdentityStatus(str, Enum):
    PENDING = "PENDING"
    PROVISIONING = "PROVISIONING"
    ACTIVE = "ACTIVE"
    DEPROVISIONING = "DEPROVISIONING"
    DEPROVISIONED = "DEPROVISIONED"
    FAILED = "FAILED"


class IdentityAccessStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
