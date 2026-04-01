create extension if not exists pgcrypto;

create table if not exists public.channel_connections (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references public.clients(id) on delete cascade,
    channel_type text not null check (channel_type in ('gmail', 'email', 'whatsapp')),
    account_identifier text,
    access_token text,
    refresh_token text,
    token_expiry timestamptz,
    metadata jsonb not null default '{}'::jsonb,
    status text not null default 'active' check (status in ('active', 'expired', 'error')),
    created_at timestamptz not null default now()
);

create table if not exists public.unified_messages (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references public.clients(id) on delete cascade,
    channel text not null,
    external_message_id text not null,
    external_thread_id text,
    sender_id text,
    sender_name text,
    message_text text,
    attachments jsonb not null default '[]'::jsonb,
    "timestamp" timestamptz not null,
    direction text not null check (direction in ('inbound', 'outbound')),
    status text not null,
    raw_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint uq_unified_messages_channel_external_message unique (channel, external_message_id)
);

create table if not exists public.conversations (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references public.clients(id) on delete cascade,
    channel text not null,
    external_thread_id text not null,
    customer_id text,
    last_message_at timestamptz,
    status text not null,
    assigned_to uuid,
    created_at timestamptz not null default now()
);

create table if not exists public.automation_settings (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references public.clients(id) on delete cascade,
    channel text not null,
    auto_reply_enabled boolean not null default false,
    confidence_threshold double precision not null default 0.8,
    created_at timestamptz not null default now()
);

create index if not exists idx_channel_connections_client_id on public.channel_connections(client_id);
create index if not exists idx_unified_messages_client_channel on public.unified_messages(client_id, channel);
create index if not exists idx_unified_messages_external_message_id on public.unified_messages(external_message_id);
create index if not exists idx_conversations_client_external_thread on public.conversations(client_id, external_thread_id);
