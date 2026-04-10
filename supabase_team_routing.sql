create extension if not exists pgcrypto;

create table if not exists public.teams (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references public.clients(id) on delete cascade,
    name text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_teams_client_name unique (client_id, name)
);

create index if not exists idx_teams_client_name
    on public.teams (client_id, name);

create table if not exists public.team_members (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references public.clients(id) on delete cascade,
    team_id uuid not null references public.teams(id) on delete cascade,
    user_id uuid not null references public.client_users(id) on delete cascade,
    role text not null default 'agent' check (role in ('agent', 'manager')),
    capacity integer not null default 10 check (capacity >= 0),
    active_tasks integer not null default 0 check (active_tasks >= 0),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_team_members_client_team_user unique (client_id, team_id, user_id)
);

create index if not exists idx_team_members_lookup
    on public.team_members (client_id, team_id, role, is_active);

create index if not exists idx_team_members_capacity
    on public.team_members (team_id, is_active, role, active_tasks, updated_at);

create table if not exists public.routing_rules (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references public.clients(id) on delete cascade,
    category text not null,
    team_id uuid not null references public.teams(id) on delete cascade,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_routing_rules_client_category unique (client_id, category)
);

create index if not exists idx_routing_rules_client_category
    on public.routing_rules (client_id, category);

alter table public.complaints
    add column if not exists team_id uuid references public.teams(id) on delete set null,
    add column if not exists assigned_user_id uuid references public.client_users(id) on delete set null;

create index if not exists idx_complaints_team
    on public.complaints (client_id, team_id);

create index if not exists idx_complaints_assigned_user
    on public.complaints (client_id, assigned_user_id);
