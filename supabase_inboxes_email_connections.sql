create extension if not exists pgcrypto;

create table if not exists public.inboxes (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    email_address text not null,
    provider_type text not null,
    access_token text null,
    refresh_token text null,
    token_expiry timestamptz null,
    metadata jsonb not null default '{}'::jsonb,
    imap_host text null,
    imap_port integer null default 993,
    imap_username text null,
    imap_password text null,
    imap_use_ssl boolean not null default true,
    last_synced_at timestamptz null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    constraint ck_inboxes_provider_type
        check (provider_type in ('gmail', 'imap')),
    constraint uq_inboxes_tenant_email_address
        unique (tenant_id, email_address)
);

create index if not exists idx_inboxes_tenant_id
    on public.inboxes (tenant_id);

create index if not exists idx_inboxes_email_address
    on public.inboxes (email_address);

alter table public.inboxes
    add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table public.inboxes
    add column if not exists imap_use_ssl boolean not null default true;

alter table public.inboxes
    add column if not exists last_synced_at timestamptz null;

alter table public.inboxes
    alter column imap_port set default 993;

comment on table public.inboxes is
    'Stores tenant-scoped email inbox connections for Gmail OAuth and generic IMAP providers.';

comment on column public.inboxes.tenant_id is
    'Workspace or tenant UUID that owns the inbox connection.';

comment on column public.inboxes.provider_type is
    'Connection provider type. Allowed values are gmail and imap.';

comment on column public.inboxes.access_token is
    'OAuth access token for provider-backed inboxes. Sensitive values should be encrypted before storage.';

comment on column public.inboxes.refresh_token is
    'OAuth refresh token for provider-backed inboxes. Sensitive values should be encrypted before storage.';

comment on column public.inboxes.metadata is
    'Provider-specific inbox sync metadata such as Gmail history cursors and OAuth scopes.';

comment on column public.inboxes.imap_password is
    'Encrypted IMAP password stored by the application for non-Gmail inboxes.';
