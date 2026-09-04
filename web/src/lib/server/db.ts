import { neon } from '@neondatabase/serverless';
import { dev } from '$app/environment';
import { env } from '$env/dynamic/private';

// The Neon serverless driver speaks Postgres over HTTP, which works inside the
// Cloudflare Workers runtime where a normal TCP client cannot, but it can
// only reach Neon's own HTTP endpoint, not a plain local Postgres. So in dev
// we use the `postgres` package instead, a real TCP client, against the
// local Postgres loaded by the ETL. The dynamic import keeps it out of the
// Cloudflare production bundle, which can't open raw TCP sockets.
type Sql = ReturnType<typeof neon>;

let client: Sql | null = null;

// Matches etl/src/etymyriad/config.py's LOCAL_DATABASE_URL: the
// standard local role/database this project's setup docs have devs
// create. Makes DATABASE_URL optional for ordinary local dev; never
// used for a real DATABASE_URL (Neon), which prod always sets via a
// Cloudflare secret.
const LOCAL_DATABASE_URL =
  'postgres://etymyriad:etymyriad@localhost:5432/etymyriad';

// Create the client lazily on first use. Deferring this (rather than building
// it at import time) keeps SvelteKit's build-time module analysis from
// requiring DATABASE_URL, which is only guaranteed to exist at runtime.
export async function getSql(): Promise<Sql> {
  if (!client) {
    const databaseUrl =
      env.DATABASE_URL ?? (dev ? LOCAL_DATABASE_URL : undefined);
    if (!databaseUrl) {
      throw new Error('DATABASE_URL is not set (see .env.example)');
    }
    if (dev) {
      const { default: postgres } = await import('postgres');
      client = postgres(databaseUrl) as unknown as Sql;
    } else {
      client = neon(databaseUrl);
    }
  }
  return client;
}
