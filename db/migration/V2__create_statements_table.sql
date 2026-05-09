CREATE TABLE statements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    statement_type TEXT NOT NULL,

    original_file_name TEXT NOT NULL,
    stored_file_path TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'uploaded',
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT statements_status_check
        CHECK (status IN ('uploaded', 'parsing', 'parsed', 'failed')),

    CONSTRAINT statements_user_id_not_blank
        CHECK (length(trim(user_id)) > 0),

    CONSTRAINT statements_account_name_not_blank
        CHECK (length(trim(account_name)) > 0),

    CONSTRAINT statements_statement_type_not_blank
        CHECK (length(trim(statement_type)) > 0),

    CONSTRAINT statements_original_file_name_not_blank
        CHECK (length(trim(original_file_name)) > 0),

    CONSTRAINT statements_stored_file_path_not_blank
        CHECK (length(trim(stored_file_path)) > 0),

    CONSTRAINT statements_id_user_id_unique
        UNIQUE (id, user_id)
);

CREATE INDEX idx_statements_user_uploaded_at
    ON statements (user_id, uploaded_at DESC);

CREATE INDEX idx_statements_user_status
    ON statements (user_id, status);