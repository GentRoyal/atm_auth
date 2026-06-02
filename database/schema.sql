CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS atm_schema;

CREATE TABLE IF NOT EXISTS atm_schema.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(100) NOT NULL,
    account_number VARCHAR(20) UNIQUE NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    card_number VARCHAR(20) UNIQUE NOT NULL,
    pin_hash TEXT NOT NULL,
    voice_sample BYTEA,
    face_encoding BYTEA,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS atm_schema.accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES atm_schema.users(id) ON DELETE CASCADE,
    account_type VARCHAR(20) NOT NULL DEFAULT 'savings',
    balance NUMERIC(15, 2) NOT NULL DEFAULT 0.00 CHECK (balance >= 0),
    currency VARCHAR(5) NOT NULL DEFAULT 'NGN',
    is_frozen BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS atm_schema.auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES atm_schema.users(id) ON DELETE SET NULL,
    card_number VARCHAR(20) NOT NULL,
    session_token TEXT UNIQUE NOT NULL,
    face_token TEXT UNIQUE,
    stage VARCHAR(30) NOT NULL DEFAULT 'card_inserted',
    voice_score DOUBLE PRECISION,
    face_score DOUBLE PRECISION,
    sms_sent_at TIMESTAMPTZ,
    voice_verified_at TIMESTAMPTZ,
    face_verified_at TIMESTAMPTZ,
    authenticated_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT auth_sessions_stage_check CHECK (
        stage IN (
            'card_inserted',
            'voice_verified',
            'sms_sent',
            'face_verified',
            'authenticated',
            'expired',
            'failed'
        )
    )
);

CREATE TABLE IF NOT EXISTS atm_schema.transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES atm_schema.auth_sessions(id) ON DELETE SET NULL,
    account_id UUID NOT NULL REFERENCES atm_schema.accounts(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL,
    amount NUMERIC(15, 2),
    recipient_account VARCHAR(20),
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT transactions_type_check CHECK (
        type IN ('withdrawal', 'deposit', 'transfer', 'balance_inquiry')
    ),
    CONSTRAINT transactions_status_check CHECK (
        status IN ('pending', 'completed', 'failed')
    )
);

CREATE TABLE IF NOT EXISTS atm_schema.auth_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES atm_schema.auth_sessions(id) ON DELETE SET NULL,
    user_id UUID REFERENCES atm_schema.users(id) ON DELETE SET NULL,
    event VARCHAR(50) NOT NULL,
    success BOOLEAN NOT NULL,
    score DOUBLE PRECISION,
    detail TEXT,
    ip_address VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_card_number ON atm_schema.users(card_number);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_face_token ON atm_schema.auth_sessions(face_token);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_session_token ON atm_schema.auth_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON atm_schema.auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON atm_schema.transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_auth_logs_session_id ON atm_schema.auth_logs(session_id);
