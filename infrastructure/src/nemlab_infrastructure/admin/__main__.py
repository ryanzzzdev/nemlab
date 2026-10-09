"""Admin account commands: ``python -m nemlab_infrastructure.admin ...``.

Server-side only — there is no public bootstrap route by design (NEM-095).

- ``bootstrap-owner --name N --email E --confirm`` creates the single
  enabled owner. Idempotent for the same email; refuses a different one.
- ``recover-owner --name N --email E --reason R --confirm`` is the audited
  recovery path: disables the current owner, revokes its sessions and
  creates the replacement. Protecting the last owner is an application
  rule enforced on ordinary revoke paths, not on this command.
- ``seed-session --email E`` prints a raw session/CSRF pair for local
  development; it refuses unless ``NEMLAB_ENVIRONMENT=development`` and
  never creates a backdoor — it is a plain session over the same checks.
- ``sign-in-link --email E`` prints a one-off sign-in URL for local
  development (the real token path, minus the mail); same development-only
  gate. ``NEMLAB_ADMIN_BASE_URL`` sets the link origin.
"""

import argparse
import os
import sys

import sqlalchemy as sa
from sqlalchemy import create_engine

from nemlab_infrastructure.admin.auth import AdminAuth, csrf_for
from nemlab_infrastructure.admin.identity import AdminIdentity, OwnerExists
from nemlab_infrastructure.settings import DatabaseSettings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nemlab-admin")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("bootstrap-owner", "recover-owner"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--name", required=True)
        cmd.add_argument("--email", required=True)
        if name == "recover-owner":
            cmd.add_argument("--reason", required=True)
        cmd.add_argument(
            "--confirm",
            action="store_true",
            help="confirm the supplied owner identity is intended",
        )
    for dev_cmd in ("seed-session", "sign-in-link"):
        cmd = commands.add_parser(
            dev_cmd,
            help=(
                "print a raw session token"
                if dev_cmd == "seed-session"
                else "print a one-off sign-in link"
            )
            + " for a local account; requires NEMLAB_ENVIRONMENT=development",
        )
        cmd.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    if args.command in ("seed-session", "sign-in-link"):
        if os.environ.get("NEMLAB_ENVIRONMENT") != "development":
            print(
                f"nemlab-admin: {args.command} requires"
                " NEMLAB_ENVIRONMENT=development — it cannot run against a"
                " production deployment",
                file=sys.stderr,
            )
            return 2
        engine = create_engine(DatabaseSettings().sqlalchemy_url())
        try:
            if args.command == "seed-session":
                raw, principal = AdminAuth(engine, base_url="").seed_session(args.email)
                print(f"session for {principal.name} ({principal.role}):")
                print(f"  token: {raw}")
                print(f"  csrf: {csrf_for(raw)}")
                print(f"  expires: {principal.expires_at.isoformat()}")
            else:
                base = os.environ.get(
                    "NEMLAB_ADMIN_BASE_URL", "http://127.0.0.1:5274/admin"
                )
                link = AdminAuth(engine, base_url=base).mint_sign_in_link(args.email)
                print(link)
            return 0
        except ValueError as ex:
            print(f"nemlab-admin: {ex}", file=sys.stderr)
            return 2
        except sa.exc.SQLAlchemyError:
            print(
                "nemlab-admin: database unavailable or V8 schema missing —"
                " run `migrate` first",
                file=sys.stderr,
            )
            return 1
        finally:
            engine.dispose()

    if not args.confirm:
        print(
            f"nemlab-admin: {args.command} refused without --confirm",
            file=sys.stderr,
        )
        return 2

    engine = create_engine(DatabaseSettings().sqlalchemy_url())
    try:
        identity = AdminIdentity(engine)
        if args.command == "bootstrap-owner":
            owner, created = identity.bootstrap_owner(args.name, args.email)
            print(
                f"owner {'created' if created else 'unchanged'}:"
                f" {owner.email} (id {owner.id})"
            )
        else:
            owner = identity.recover_owner(args.name, args.email, args.reason)
            print(f"owner recovered: {owner.email} (id {owner.id})")
        return 0
    except OwnerExists as ex:
        print(f"nemlab-admin: {ex}", file=sys.stderr)
        return 1
    except ValueError as ex:
        print(f"nemlab-admin: {ex}", file=sys.stderr)
        return 2
    except sa.exc.SQLAlchemyError:
        print(
            "nemlab-admin: database unavailable or V8 schema missing —"
            " run `migrate` first",
            file=sys.stderr,
        )
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
