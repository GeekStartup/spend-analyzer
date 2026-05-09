CREATE TABLE statements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id TEXT NOT NULL,

    institution TEXT,
    account_type TEXT,
    account_name TEXT,
    statement_format TEXT,

    original_file_name TEXT NOT NULL,
    stored_file_path TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'UPLOADED',
    parse_confidence NUMERIC(5, 4),
    review_required BOOLEAN NOT NULL DEFAULT FALSE,

    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT statements_status_check
        CHECK (status IN ('UPLOADED', 'PARSING', 'PARSED', 'FAILED', 'NEEDS_REVIEW')),

    CONSTRAINT statements_parse_confidence_range_check
        CHECK (parse_confidence IS NULL OR parse_confidence BETWEEN 0 AND 1),

    CONSTRAINT statements_user_id_not_blank
        CHECK (length(trim(user_id)) > 0),

    CONSTRAINT statements_institution_not_blank
        CHECK (institution IS NULL OR length(trim(institution)) > 0),

    CONSTRAINT statements_account_type_not_blank
        CHECK (account_type IS NULL OR length(trim(account_type)) > 0),

    CONSTRAINT statements_account_name_not_blank
        CHECK (account_name IS NULL OR length(trim(account_name)) > 0),

    CONSTRAINT statements_statement_format_not_blank
        CHECK (statement_format IS NULL OR length(trim(statement_format)) > 0),

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

CREATE INDEX idx_statements_user_review_required
    ON statements (user_id, review_required);