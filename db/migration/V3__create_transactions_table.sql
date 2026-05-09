CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id TEXT NOT NULL,
    statement_id UUID NOT NULL,

    transaction_date DATE NOT NULL,
    description TEXT NOT NULL,
    merchant TEXT,
    category TEXT,

    amount NUMERIC(14, 2) NOT NULL,
    transaction_type TEXT NOT NULL,

    account_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT transactions_statement_user_fk
        FOREIGN KEY (statement_id, user_id)
        REFERENCES statements (id, user_id)
        ON DELETE CASCADE,

    CONSTRAINT transactions_type_check
        CHECK (transaction_type IN ('debit', 'credit')),

    CONSTRAINT transactions_amount_non_negative_check
        CHECK (amount >= 0),

    CONSTRAINT transactions_user_id_not_blank
        CHECK (length(trim(user_id)) > 0),

    CONSTRAINT transactions_description_not_blank
        CHECK (length(trim(description)) > 0),

    CONSTRAINT transactions_account_name_not_blank
        CHECK (length(trim(account_name)) > 0)
);

CREATE INDEX idx_transactions_user_date
    ON transactions (user_id, transaction_date DESC);

CREATE INDEX idx_transactions_user_category
    ON transactions (user_id, category);

CREATE INDEX idx_transactions_user_merchant
    ON transactions (user_id, merchant);

CREATE INDEX idx_transactions_statement_id
    ON transactions (statement_id);