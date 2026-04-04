from common.enums import AccountStatus, CardStatus, ClientStatus, TicketStatus, TransferStatus

CLIENT_TRANSITIONS = {
    ClientStatus.NEW: {ClientStatus.PENDING_VERIFICATION},
    ClientStatus.PENDING_VERIFICATION: {ClientStatus.ACTIVE, ClientStatus.BLOCKED},
    ClientStatus.ACTIVE: {ClientStatus.SUSPENDED, ClientStatus.BLOCKED},
    ClientStatus.SUSPENDED: {ClientStatus.ACTIVE, ClientStatus.BLOCKED},
    ClientStatus.BLOCKED: {ClientStatus.SUSPENDED, ClientStatus.CLOSED},
    ClientStatus.CLOSED: {ClientStatus.ARCHIVED},
    ClientStatus.ARCHIVED: set(),
}

ACCOUNT_TRANSITIONS = {
    AccountStatus.DRAFT: {AccountStatus.PENDING_APPROVAL},
    AccountStatus.PENDING_APPROVAL: {AccountStatus.ACTIVE, AccountStatus.BLOCKED},
    AccountStatus.ACTIVE: {AccountStatus.PARTIALLY_RESTRICTED, AccountStatus.BLOCKED, AccountStatus.CLOSED},
    AccountStatus.PARTIALLY_RESTRICTED: {AccountStatus.ACTIVE, AccountStatus.BLOCKED, AccountStatus.CLOSED},
    AccountStatus.BLOCKED: {AccountStatus.ACTIVE},
    AccountStatus.CLOSED: set(),
}

CARD_TRANSITIONS = {
    CardStatus.ORDERED: {CardStatus.PERSONALIZED},
    CardStatus.PERSONALIZED: {CardStatus.ISSUED},
    CardStatus.ISSUED: {CardStatus.ACTIVE},
    CardStatus.ACTIVE: {CardStatus.TEMP_BLOCKED, CardStatus.BLOCKED, CardStatus.EXPIRED},
    CardStatus.TEMP_BLOCKED: {CardStatus.ACTIVE, CardStatus.BLOCKED},
    CardStatus.BLOCKED: {CardStatus.CLOSED},
    CardStatus.EXPIRED: {CardStatus.CLOSED},
    CardStatus.CLOSED: set(),
}

TRANSFER_TRANSITIONS = {
    TransferStatus.DRAFT: {TransferStatus.CREATED},
    TransferStatus.CREATED: {TransferStatus.PENDING_ANTI_FRAUD, TransferStatus.CANCELLED},
    TransferStatus.PENDING_ANTI_FRAUD: {TransferStatus.PENDING_EXECUTION, TransferStatus.FAILED},
    TransferStatus.PENDING_EXECUTION: {TransferStatus.PROCESSING, TransferStatus.CANCELLED},
    TransferStatus.PROCESSING: {TransferStatus.COMPLETED, TransferStatus.FAILED},
    TransferStatus.COMPLETED: {TransferStatus.REVERSED},
    TransferStatus.FAILED: set(),
    TransferStatus.CANCELLED: set(),
    TransferStatus.REVERSED: set(),
}

TICKET_TRANSITIONS = {
    TicketStatus.NEW: {TicketStatus.IN_REVIEW},
    TicketStatus.IN_REVIEW: {
        TicketStatus.WAITING_FOR_CLIENT,
        TicketStatus.WAITING_FOR_EMPLOYEE,
        TicketStatus.RESOLVED,
        TicketStatus.REJECTED,
    },
    TicketStatus.WAITING_FOR_CLIENT: {TicketStatus.IN_REVIEW},
    TicketStatus.WAITING_FOR_EMPLOYEE: {TicketStatus.IN_REVIEW},
    TicketStatus.RESOLVED: {TicketStatus.CLOSED},
    TicketStatus.REJECTED: {TicketStatus.CLOSED},
    TicketStatus.CLOSED: set(),
}


def ensure_transition(current: str, target: str, transition_map: dict[str, set[str]]) -> bool:
    return target in transition_map.get(current, set())
