import typer

app = typer.Typer(
    help="Koel management CLI.",
    no_args_is_help=True,
    add_completion=False,
)

admin = typer.Typer(help="Admin management commands.", no_args_is_help=True)
app.add_typer(admin, name="admin")


def _set_role_or_exit(email: str, role: str, past_tense: str, audit_action: str) -> None:
    from koel.db.audit import record_audit
    from koel.db.auth import find_user_by_email, set_user_role
    from koel.db.session import session_scope

    normalized = email.lower()
    with session_scope() as session:
        existing = find_user_by_email(session, normalized)
        if existing is None:
            typer.secho(f"no user with email {email}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        if existing.role == role:
            typer.secho(
                f"{email} is already {role} — nothing to do", fg=typer.colors.YELLOW
            )
            return
        updated = set_user_role(session, email=normalized, role=role)
        assert updated is not None  # we just confirmed the row exists
        record_audit(
            session,
            action=audit_action,
            subject_type="user",
            subject_id=updated.id,
            meta={"email": normalized, "role": role, "via": "cli"},
        )
        typer.secho(
            f"{past_tense} {updated.email} (role={updated.role})",
            fg=typer.colors.GREEN,
        )


@admin.command("promote")
def admin_promote(email: str) -> None:
    """Promote a user to the admin role."""
    from koel.db.audit import ACTION_USER_PROMOTE

    _set_role_or_exit(email, role="admin", past_tense="promoted", audit_action=ACTION_USER_PROMOTE)


@admin.command("demote")
def admin_demote(email: str) -> None:
    """Demote an admin back to the regular user role."""
    from koel.db.audit import ACTION_USER_DEMOTE

    _set_role_or_exit(email, role="user", past_tense="demoted", audit_action=ACTION_USER_DEMOTE)


@admin.command("list")
def admin_list() -> None:
    """List all users currently holding the admin role."""
    from koel.db.auth import list_admins
    from koel.db.session import session_scope

    with session_scope() as session:
        rows = list_admins(session)

    if not rows:
        typer.secho("no admins", fg=typer.colors.YELLOW)
        return
    for row in rows:
        active = "active" if row.is_active else "inactive"
        typer.echo(f"{row.email:40} {row.id}  [{active}]")


@admin.command("audit")
def admin_audit(
    limit: int = typer.Option(50, help="Max entries to show (most recent first)."),
    action: str = typer.Option("", help="Filter to a single action, e.g. user.promote."),
) -> None:
    """Show the most recent audit-log entries."""
    from koel.db.audit import list_recent_audit
    from koel.db.session import session_scope

    with session_scope() as session:
        entries = list_recent_audit(session, limit=limit, action=action or None)

    if not entries:
        typer.secho("no audit entries", fg=typer.colors.YELLOW)
        return
    for e in entries:
        actor = str(e.actor_user_id) if e.actor_user_id else "system"
        subject = f"{e.subject_type}:{e.subject_id}" if e.subject_type else "—"
        typer.echo(f"{e.occurred_at:%Y-%m-%d %H:%M:%S}  {e.action:24} {actor}  {subject}")


db = typer.Typer(help="Database management commands.", no_args_is_help=True)
app.add_typer(db, name="db")


@db.command("seed")
def db_seed() -> None:
    """Idempotently seed currencies + sources from packaged JSON."""
    from koel.db.seed import seed_all
    from koel.db.session import session_scope

    with session_scope() as session:
        counts = seed_all(session)
        typer.secho(f"seeded: {counts}", fg=typer.colors.GREEN)


@db.command("ensure-partitions")
def db_ensure_partitions(lookahead: int = 2) -> None:
    """Create current + forward monthly partitions if missing."""
    from koel.db.partitions import ensure_partitions
    from koel.db.session import get_engine

    with get_engine().begin() as conn:
        created = ensure_partitions(conn, lookahead=lookahead)
    typer.secho(f"ensured {len(created)} partitions", fg=typer.colors.GREEN)


@db.command("drop-old-partitions")
def db_drop_old_partitions() -> None:
    """Drop partitions older than each table's retention window."""
    from koel.db.partitions import drop_expired_partitions
    from koel.db.session import get_engine

    with get_engine().begin() as conn:
        dropped = drop_expired_partitions(conn)
    if dropped:
        typer.secho(f"dropped {len(dropped)}: {dropped}", fg=typer.colors.YELLOW)
    else:
        typer.secho("no expired partitions", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
