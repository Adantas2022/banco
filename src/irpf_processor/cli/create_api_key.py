#!/usr/bin/env python3
import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone

from irpf_processor.domain.entities import ApiKey
from irpf_processor.domain.enums import AuthScope
from irpf_processor.infrastructure.persistence import MongoApiKeyRepository
from irpf_processor.infrastructure.persistence.database import init_database, get_database, close_database


async def create_api_key(
    tenant_id: str,
    name: str,
    scopes: list[str],
    expires_days: int | None = None,
) -> tuple[ApiKey, str]:
    await init_database()
    db = await get_database()
    repo = MongoApiKeyRepository(db)

    expires_at = None
    if expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    api_key, raw_key = ApiKey.create(
        tenant_id=tenant_id,
        name=name,
        scopes=scopes,
        expires_at=expires_at,
    )

    await repo.create(api_key)
    await close_database()

    return api_key, raw_key


def main():
    parser = argparse.ArgumentParser(
        description="Create an API Key for IRPF Processor"
    )
    parser.add_argument(
        "--tenant-id",
        required=True,
        help="Tenant ID for the API key",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Name/description for the API key",
    )
    parser.add_argument(
        "--scopes",
        nargs="+",
        default=None,
        help=f"Scopes for the API key. Available: {AuthScope.all_scopes()}",
    )
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Create an admin key with all scopes including admin:keys",
    )
    parser.add_argument(
        "--expires-days",
        type=int,
        default=None,
        help="Number of days until the key expires (optional)",
    )

    args = parser.parse_args()

    if args.admin:
        scopes = AuthScope.all_scopes()
    elif args.scopes:
        scopes = args.scopes
        invalid = set(scopes) - set(AuthScope.all_scopes())
        if invalid:
            print(f"ERROR: Invalid scopes: {invalid}")
            print(f"Available scopes: {AuthScope.all_scopes()}")
            sys.exit(1)
    else:
        scopes = AuthScope.default_scopes()

    print(f"Creating API key for tenant: {args.tenant_id}")
    print(f"Name: {args.name}")
    print(f"Scopes: {scopes}")
    if args.expires_days:
        print(f"Expires in: {args.expires_days} days")

    api_key, raw_key = asyncio.run(
        create_api_key(
            tenant_id=args.tenant_id,
            name=args.name,
            scopes=scopes,
            expires_days=args.expires_days,
        )
    )

    print("\n" + "=" * 60)
    print("API KEY CREATED SUCCESSFULLY")
    print("=" * 60)
    print(f"API Key ID: {api_key.api_key_id}")
    print(f"Tenant ID:  {api_key.tenant_id}")
    print(f"Name:       {api_key.name}")
    print(f"Scopes:     {api_key.scopes}")
    print(f"Expires:    {api_key.expires_at or 'Never'}")
    print("-" * 60)
    print("RAW API KEY (save this, it will not be shown again):")
    print(f"\n  {raw_key}\n")
    print("-" * 60)
    print("Usage example:")
    print(f'  curl -H "Authorization: Bearer {raw_key}" http://localhost:8000/v1/auth/me')
    print("=" * 60)


if __name__ == "__main__":
    main()
