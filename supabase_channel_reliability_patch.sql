with ranked_conversations as (
    select
        id,
        row_number() over (
            partition by client_id, channel, external_thread_id
            order by coalesce(last_message_at, created_at) desc, created_at desc, id desc
        ) as row_rank
    from public.conversations
)
delete from public.conversations
where id in (
    select id
    from ranked_conversations
    where row_rank > 1
);

create unique index if not exists uq_conversations_client_channel_thread
    on public.conversations (client_id, channel, external_thread_id);

alter table public.unified_messages
    add column if not exists retry_count integer not null default 0,
    add column if not exists last_error text,
    add column if not exists next_retry_at timestamptz;

create table if not exists public.message_events (
    id uuid primary key default gen_random_uuid(),
    message_id uuid,
    event_type text not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_unified_messages_status
    on public.unified_messages (status);

create index if not exists idx_unified_messages_next_retry_at
    on public.unified_messages (next_retry_at);

create index if not exists idx_conversations_last_message_at
    on public.conversations (last_message_at);

create index if not exists idx_message_events_message_id
    on public.message_events (message_id);

create index if not exists idx_message_events_event_type
    on public.message_events (event_type);
