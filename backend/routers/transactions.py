"""
routers/transactions.py
Transaction endpoints (only accessible after full authentication):
  POST /transactions/          – perform a transaction
  GET  /transactions/history   – list recent transactions for the session
"""
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from backend.database import database, auth_sessions, accounts, transactions, users
from backend.models.schemas import (
    TransactionRequest, TransactionResponse, TransactionType, SessionStage
)
from backend.utils.security import is_expired

router = APIRouter(prefix="/transactions", tags=["Transactions"])
logger = logging.getLogger(__name__)


async def _require_authenticated_session(session_id: str):
    """Validate session is fully authenticated and not expired."""
    session = await database.fetch_one(
        auth_sessions.select().where(auth_sessions.c.id == session_id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if is_expired(session["expires_at"]):
        raise HTTPException(status_code=410, detail="Session expired.")
    if session["stage"] != SessionStage.authenticated:
        raise HTTPException(
            status_code=403,
            detail=f"Not authenticated. Current stage: {session['stage']}"
        )
    return session


@router.post("/", response_model=TransactionResponse)
async def perform_transaction(body: TransactionRequest):
    session = await _require_authenticated_session(body.session_id)

    # Get user's account
    account = await database.fetch_one(
        accounts.select().where(accounts.c.user_id == session["user_id"])
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    if account["is_frozen"]:
        raise HTTPException(status_code=403, detail="Account is frozen.")

    tx_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    balance_after = float(account["balance"])

    # ── Balance Inquiry ──────────────────────────────────
    if body.type == TransactionType.balance_inquiry:
        await database.execute(
            transactions.insert().values(
                id=tx_id,
                session_id=body.session_id,
                account_id=str(account["id"]),
                type="balance_inquiry",
                amount=None,
                status="completed",
                description="Balance inquiry",
                created_at=now,
            )
        )
        return TransactionResponse(
            transaction_id=tx_id,
            type=body.type,
            amount=None,
            balance_after=balance_after,
            status="completed",
            message=f"Your balance is ₦{balance_after:,.2f}",
            created_at=now,
        )

    # ── Withdrawal ────────────────────────────────────────
    elif body.type == TransactionType.withdrawal:
        amount = body.amount or 0
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive.")
        if amount > balance_after:
            raise HTTPException(status_code=400, detail="Insufficient funds.")
        if amount > 150_000:
            raise HTTPException(status_code=400, detail="Exceeds single withdrawal limit of ₦150,000.")

        balance_after -= amount
        await database.execute(
            accounts.update()
            .where(accounts.c.id == str(account["id"]))
            .values(balance=balance_after, updated_at=now)
        )
        await database.execute(
            transactions.insert().values(
                id=tx_id, session_id=body.session_id,
                account_id=str(account["id"]),
                type="withdrawal", amount=amount,
                status="completed",
                description=body.description or "ATM Withdrawal",
                created_at=now,
            )
        )
        return TransactionResponse(
            transaction_id=tx_id, type=body.type, amount=amount,
            balance_after=balance_after, status="completed",
            message=f"₦{amount:,.2f} dispensed. Remaining balance: ₦{balance_after:,.2f}",
            created_at=now,
        )

    # ── Deposit ───────────────────────────────────────────
    elif body.type == TransactionType.deposit:
        amount = body.amount or 0
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive.")

        balance_after += amount
        await database.execute(
            accounts.update()
            .where(accounts.c.id == str(account["id"]))
            .values(balance=balance_after, updated_at=now)
        )
        await database.execute(
            transactions.insert().values(
                id=tx_id, session_id=body.session_id,
                account_id=str(account["id"]),
                type="deposit", amount=amount,
                status="completed",
                description=body.description or "ATM Deposit",
                created_at=now,
            )
        )
        return TransactionResponse(
            transaction_id=tx_id, type=body.type, amount=amount,
            balance_after=balance_after, status="completed",
            message=f"₦{amount:,.2f} deposited. New balance: ₦{balance_after:,.2f}",
            created_at=now,
        )

    # ── Transfer ──────────────────────────────────────────
    elif body.type == TransactionType.transfer:
        amount = body.amount or 0
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive.")
        if not body.recipient_account:
            raise HTTPException(status_code=400, detail="Recipient account required.")
        if amount > balance_after:
            raise HTTPException(status_code=400, detail="Insufficient funds.")

        # Check recipient exists
        recipient_user = await database.fetch_one(
            users.select().where(users.c.account_number == body.recipient_account)
        )
        if not recipient_user:
            raise HTTPException(status_code=404, detail="Recipient account not found.")

        recipient_account = await database.fetch_one(
            accounts.select().where(accounts.c.user_id == str(recipient_user["id"]))
        )

        balance_after -= amount
        # Debit sender
        await database.execute(
            accounts.update()
            .where(accounts.c.id == str(account["id"]))
            .values(balance=balance_after, updated_at=now)
        )
        # Credit recipient
        await database.execute(
            accounts.update()
            .where(accounts.c.id == str(recipient_account["id"]))
            .values(balance=recipient_account["balance"] + amount, updated_at=now)
        )
        await database.execute(
            transactions.insert().values(
                id=tx_id, session_id=body.session_id,
                account_id=str(account["id"]),
                type="transfer", amount=amount,
                recipient_account=body.recipient_account,
                status="completed",
                description=body.description or f"Transfer to {body.recipient_account}",
                created_at=now,
            )
        )
        return TransactionResponse(
            transaction_id=tx_id, type=body.type, amount=amount,
            balance_after=balance_after, status="completed",
            message=f"₦{amount:,.2f} sent to {recipient_user['full_name']}. Balance: ₦{balance_after:,.2f}",
            created_at=now,
        )

    raise HTTPException(status_code=400, detail="Unknown transaction type.")


@router.get("/history")
async def get_history(session_id: str, limit: int = 10):
    session = await _require_authenticated_session(session_id)
    account = await database.fetch_one(
        accounts.select().where(accounts.c.user_id == session["user_id"])
    )
    rows = await database.fetch_all(
        transactions.select()
        .where(transactions.c.account_id == str(account["id"]))
        .order_by(transactions.c.created_at.desc())
        .limit(limit)
    )
    return [dict(r) for r in rows]