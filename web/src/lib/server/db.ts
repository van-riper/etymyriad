import { neon } from '@neondatabase/serverless';
import { dev } from '$app/environment';
import { env } from '$env/dynamic/private';

// The Neon serverless driver speaks Postgres over HTTP, which works inside the
// Cloudflare Workers runtime where a normal TCP client cannot -- but it can
// only reach Neon's own HTTP endpoint, not a plain local Postgres. So in dev
// we use the `postgres` package instead, a real TCP client, against the
// local Postgres loaded by the ETL. The dynamic import keeps it out of the
// Cloudflare production bundle, which can't open raw TCP sockets.
type Sql = ReturnType<typeof neon>;

let client: Sql | null = null;

// Create the client lazily on first use. Deferring this (rather than building
// it at import time) keeps SvelteKit's build-time module analysis from
// requiring DATABASE_URL, which is only guaranteed to exist at runtime.
export async function getSql(): Promise<Sql> {
  if (!client) {
    if (!env.DATABASE_URL) {
      throw new Error('DATABASE_URL is not set (see .env.example)');
    }
    if (dev) {
      const { default: postgres } = await import('postgres');
      client = postgres(env.DATABASE_URL) as unknown as Sql;
    } else {
      client = neon(env.DATABASE_URL);
    }
  }
  return client;
}
