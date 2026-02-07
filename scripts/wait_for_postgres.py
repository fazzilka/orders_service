import asyncio
import os

import asyncpg


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url.removeprefix("postgresql+asyncpg://")
    return url


async def wait_for_postgres(database_url: str, timeout_seconds: int) -> None:
    database_url = _normalize_database_url(database_url)
    deadline = asyncio.get_running_loop().time() + timeout_seconds

    while True:
        try:
            conn = await asyncpg.connect(database_url)
            await conn.close()
            return
        except Exception:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(1)


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    timeout_seconds = int(os.getenv("POSTGRES_WAIT_TIMEOUT", "60"))
    asyncio.run(wait_for_postgres(database_url, timeout_seconds))


if __name__ == "__main__":
    main()

