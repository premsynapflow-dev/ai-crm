create extension if not exists pgcrypto;

create table if not exists public.rbi_categories (
    id uuid primary key default gen_random_uuid(),
    category_code text not null,
    category_name text not null,
    subcategory_code text not null,
    subcategory_name text,
    tat_days integer not null default 30,
    description text,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create unique index if not exists uq_rbi_categories_category_subcategory
    on public.rbi_categories (category_code, subcategory_code);

insert into public.rbi_categories (
    category_code,
    category_name,
    subcategory_code,
    subcategory_name,
    tat_days,
    description,
    is_active
)
select
    category_code,
    category_name,
    subcategory_code,
    subcategory_name,
    tat_days,
    description,
    is_active
from public.rbi_complaint_categories
on conflict do nothing;

alter table public.complaints
    add column if not exists rbi_category_code text,
    add column if not exists tat_due_at timestamptz,
    add column if not exists tat_status text not null default 'not_applicable',
    add column if not exists tat_breached_at timestamptz;

create index if not exists idx_complaints_rbi_category_code
    on public.complaints (rbi_category_code);

create index if not exists idx_complaints_tat_due_at
    on public.complaints (tat_due_at);

update public.complaints as c
set
    rbi_category_code = coalesce(c.rbi_category_code, rc.category_code),
    tat_due_at = coalesce(c.tat_due_at, rc.tat_due_date),
    tat_status = case
        when c.tat_status is not null and c.tat_status <> 'not_applicable' then c.tat_status
        else coalesce(rc.tat_status, 'within_tat')
    end,
    tat_breached_at = coalesce(
        c.tat_breached_at,
        case
            when rc.tat_status = 'breached' then rc.tat_due_date
            else null
        end
    )
from public.rbi_complaints as rc
where rc.complaint_id = c.id;

create table if not exists public.escalations (
    id uuid primary key default gen_random_uuid(),
    ticket_id uuid not null references public.complaints(id) on delete cascade,
    level integer not null default 1,
    escalated_to text,
    reason text,
    created_at timestamptz not null default now()
);

create index if not exists idx_escalations_ticket_created
    on public.escalations (ticket_id, created_at desc);

create table if not exists public.audit_logs (
    id uuid primary key default gen_random_uuid(),
    entity_type text not null,
    entity_id uuid not null,
    action text not null,
    performed_by text,
    old_value jsonb,
    new_value jsonb,
    "timestamp" timestamptz not null default now()
);

create index if not exists idx_audit_logs_entity
    on public.audit_logs (entity_type, entity_id, "timestamp" desc);

create index if not exists idx_audit_logs_action
    on public.audit_logs (action, "timestamp" desc);

create or replace function public.prevent_audit_logs_mutation()
returns trigger
language plpgsql
as $$
begin
    raise exception 'audit_logs rows are immutable';
end;
$$;

do $$
begin
    if not exists (
        select 1
        from pg_trigger
        where tgname = 'trg_audit_logs_no_update'
    ) then
        create trigger trg_audit_logs_no_update
        before update on public.audit_logs
        for each row
        execute function public.prevent_audit_logs_mutation();
    end if;

    if not exists (
        select 1
        from pg_trigger
        where tgname = 'trg_audit_logs_no_delete'
    ) then
        create trigger trg_audit_logs_no_delete
        before delete on public.audit_logs
        for each row
        execute function public.prevent_audit_logs_mutation();
    end if;
end $$;
