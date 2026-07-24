#!/bin/sh
set -e

echo "Running schema migration..."
python -c "
import asyncio, asyncpg, os

async def migrate():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    with open('/app/sql/migrations/001_initial_schema.sql') as f:
        sql = f.read()
    await conn.execute(sql)
    await conn.close()
    print('Migration complete.')

asyncio.run(migrate())
"

echo "Starting API..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
