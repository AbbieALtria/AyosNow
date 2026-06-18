-- AYOSNOW MVP Core Database Migration 001
-- PostgreSQL 15+

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE auth_user (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_type varchar(30) NOT NULL CHECK (user_type IN ('customer','provider','admin')),
    mobile varchar(30) UNIQUE,
    email varchar(255) UNIQUE,
    password_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    mobile_verified_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE auth_role (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(50) NOT NULL UNIQUE,
    name varchar(100) NOT NULL
);

CREATE TABLE auth_permission (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(100) NOT NULL UNIQUE,
    name varchar(150) NOT NULL
);

CREATE TABLE auth_user_role (
    user_id uuid NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    role_id uuid NOT NULL REFERENCES auth_role(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE auth_role_permission (
    role_id uuid NOT NULL REFERENCES auth_role(id) ON DELETE CASCADE,
    permission_id uuid NOT NULL REFERENCES auth_permission(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE auth_otp (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES auth_user(id) ON DELETE CASCADE,
    mobile varchar(30) NOT NULL,
    purpose varchar(40) NOT NULL CHECK (purpose IN ('register','login','password_reset','payout','profile_change')),
    otp_hash text NOT NULL,
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts integer NOT NULL DEFAULT 5 CHECK (max_attempts > 0),
    expires_at timestamptz NOT NULL,
    verified_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE geo_region (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(120) NOT NULL,
    is_active boolean NOT NULL DEFAULT true
);

CREATE TABLE geo_city (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    region_id uuid NOT NULL REFERENCES geo_region(id),
    name varchar(120) NOT NULL,
    is_active boolean NOT NULL DEFAULT true
);

CREATE TABLE geo_barangay (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id uuid NOT NULL REFERENCES geo_city(id),
    name varchar(120) NOT NULL,
    is_active boolean NOT NULL DEFAULT true
);

CREATE TABLE cust_customer (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE RESTRICT,
    first_name varchar(100) NOT NULL,
    last_name varchar(100) NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','closed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE cust_address (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id uuid NOT NULL REFERENCES cust_customer(id) ON DELETE CASCADE,
    label varchar(80) NOT NULL,
    region_id uuid NOT NULL REFERENCES geo_region(id),
    city_id uuid NOT NULL REFERENCES geo_city(id),
    barangay_id uuid REFERENCES geo_barangay(id),
    line1 varchar(255) NOT NULL,
    landmark varchar(255),
    latitude numeric(10,7),
    longitude numeric(10,7),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE prov_provider (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE RESTRICT,
    provider_type varchar(30) NOT NULL CHECK (provider_type IN ('individual','team','company')),
    display_name varchar(160) NOT NULL,
    city_id uuid NOT NULL REFERENCES geo_city(id),
    verification_status varchar(30) NOT NULL DEFAULT 'pending'
        CHECK (verification_status IN ('pending','under_review','approved','rejected','suspended')),
    verification_reason text,
    verified_by uuid REFERENCES auth_user(id),
    verified_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE prov_document (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id uuid NOT NULL REFERENCES prov_provider(id) ON DELETE CASCADE,
    document_type varchar(60) NOT NULL,
    file_url text NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','approved','rejected')),
    review_reason text,
    reviewed_by uuid REFERENCES auth_user(id),
    reviewed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE svc_category (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(120) NOT NULL,
    description text,
    is_active boolean NOT NULL DEFAULT true,
    sort_order integer NOT NULL DEFAULT 0
);

CREATE TABLE svc_item (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id uuid NOT NULL REFERENCES svc_category(id),
    name varchar(140) NOT NULL,
    description text,
    pricing_model varchar(30) NOT NULL CHECK (pricing_model IN ('fixed','estimated','quote_required')),
    base_price numeric(12,2) CHECK (base_price IS NULL OR base_price >= 0),
    is_active boolean NOT NULL DEFAULT true
);

CREATE TABLE prov_skill (
    provider_id uuid NOT NULL REFERENCES prov_provider(id) ON DELETE CASCADE,
    service_item_id uuid NOT NULL REFERENCES svc_item(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (provider_id, service_item_id)
);

CREATE TABLE book_booking (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id uuid NOT NULL REFERENCES cust_customer(id),
    service_item_id uuid NOT NULL REFERENCES svc_item(id),
    customer_address_id uuid NOT NULL REFERENCES cust_address(id),
    service_snapshot jsonb NOT NULL,
    address_snapshot jsonb NOT NULL,
    requested_schedule timestamptz NOT NULL,
    description text NOT NULL,
    status varchar(40) NOT NULL DEFAULT 'pending_dispatch'
        CHECK (status IN ('draft','submitted','pending_dispatch','assigned','provider_accepted','provider_declined','in_progress','completed_by_provider','confirmed_completed','cancelled','disputed')),
    cancellation_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE book_status_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id uuid NOT NULL REFERENCES book_booking(id) ON DELETE CASCADE,
    from_status varchar(40),
    to_status varchar(40) NOT NULL,
    reason text,
    actor_user_id uuid REFERENCES auth_user(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE book_assignment (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id uuid NOT NULL REFERENCES book_booking(id) ON DELETE CASCADE,
    provider_id uuid NOT NULL REFERENCES prov_provider(id),
    status varchar(30) NOT NULL DEFAULT 'assigned'
        CHECK (status IN ('assigned','accepted','declined','cancelled','completed')),
    assigned_by uuid NOT NULL REFERENCES auth_user(id),
    assignment_reason text,
    provider_response_reason text,
    responded_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX ux_book_assignment_active
ON book_assignment(booking_id)
WHERE status IN ('assigned','accepted');

CREATE TABLE fin_payment (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id uuid NOT NULL REFERENCES book_booking(id),
    customer_id uuid NOT NULL REFERENCES cust_customer(id),
    amount numeric(12,2) NOT NULL CHECK (amount >= 0),
    currency char(3) NOT NULL DEFAULT 'PHP',
    status varchar(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','processing','captured','failed','cancelled','refunded','partially_refunded')),
    gateway varchar(60) NOT NULL,
    gateway_reference varchar(160),
    idempotency_key varchar(160) NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fin_gateway_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id uuid REFERENCES fin_payment(id),
    gateway varchar(60) NOT NULL,
    event_id varchar(160) NOT NULL,
    event_type varchar(100) NOT NULL,
    payload jsonb NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (gateway, event_id)
);

CREATE TABLE fin_wallet_ledger (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id uuid NOT NULL REFERENCES prov_provider(id),
    source_type varchar(60) NOT NULL,
    source_id uuid NOT NULL,
    entry_type varchar(60) NOT NULL
        CHECK (entry_type IN ('payment_captured','provider_earning','commission','refund','adjustment','payout_requested','payout_released','payout_failed','hold','hold_released')),
    direction varchar(10) NOT NULL CHECK (direction IN ('credit','debit')),
    amount numeric(12,2) NOT NULL CHECK (amount >= 0),
    currency char(3) NOT NULL DEFAULT 'PHP',
    is_available boolean NOT NULL DEFAULT true,
    notes text,
    created_by uuid REFERENCES auth_user(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fin_payout (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id uuid NOT NULL REFERENCES prov_provider(id),
    requested_amount numeric(12,2) NOT NULL CHECK (requested_amount > 0),
    currency char(3) NOT NULL DEFAULT 'PHP',
    status varchar(30) NOT NULL DEFAULT 'requested'
        CHECK (status IN ('requested','under_review','approved','rejected','released','failed')),
    provider_notes text,
    finance_reason text,
    reviewed_by uuid REFERENCES auth_user(id),
    reviewed_at timestamptz,
    released_at timestamptz,
    payout_reference varchar(160),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE qa_complaint (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id uuid NOT NULL REFERENCES book_booking(id),
    opened_by uuid NOT NULL REFERENCES auth_user(id),
    status varchar(40) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','under_review','awaiting_customer','awaiting_provider','resolved','rejected','escalated')),
    category varchar(80) NOT NULL,
    description text NOT NULL,
    resolution text,
    financial_impact numeric(12,2) DEFAULT 0 CHECK (financial_impact >= 0),
    resolved_by uuid REFERENCES auth_user(id),
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE qa_complaint_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id uuid NOT NULL REFERENCES qa_complaint(id) ON DELETE CASCADE,
    uploaded_by uuid NOT NULL REFERENCES auth_user(id),
    file_url text NOT NULL,
    file_type varchar(80),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE aud_audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id uuid REFERENCES auth_user(id),
    action varchar(120) NOT NULL,
    entity_type varchar(80) NOT NULL,
    entity_id uuid,
    before_data jsonb,
    after_data jsonb,
    ip_address inet,
    user_agent text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_auth_otp_mobile_purpose ON auth_otp(mobile, purpose, created_at DESC);
CREATE INDEX ix_cust_address_customer_active ON cust_address(customer_id, is_active);
CREATE INDEX ix_provider_status_city ON prov_provider(verification_status, city_id);
CREATE INDEX ix_booking_status_schedule ON book_booking(status, requested_schedule);
CREATE INDEX ix_booking_customer_created ON book_booking(customer_id, created_at DESC);
CREATE INDEX ix_assignment_provider_status ON book_assignment(provider_id, status);
CREATE INDEX ix_payment_booking_status ON fin_payment(booking_id, status);
CREATE INDEX ix_wallet_provider_created ON fin_wallet_ledger(provider_id, created_at DESC);
CREATE INDEX ix_payout_provider_status ON fin_payout(provider_id, status);
CREATE INDEX ix_complaint_status_created ON qa_complaint(status, created_at DESC);
CREATE INDEX ix_audit_entity ON aud_audit_log(entity_type, entity_id, created_at DESC);
CREATE INDEX ix_audit_actor ON aud_audit_log(actor_user_id, created_at DESC);

CREATE OR REPLACE FUNCTION prevent_wallet_ledger_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'fin_wallet_ledger is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_wallet_ledger_update
BEFORE UPDATE OR DELETE ON fin_wallet_ledger
FOR EACH ROW EXECUTE FUNCTION prevent_wallet_ledger_mutation();

