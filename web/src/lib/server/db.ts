import { neon } from '@neondatabase/serverless';
import { env } from '$env/dynamic/private';

// The Neon serverless driver speaks Postgres over HTTP, which works inside the
// Cloudflare Workers runtime where a normal TCP client cannot. `env` resolves
// from the local .env in dev and from Cloudflare secrets in production.
//
// LOCAL DEV NOTE: point DATABASE_URL at a Neon branch for web-app development.
// The local podman Postgres is for the Python ETL's bulk-load iteration;
// the serverless driver talks to Neon's HTTP endpoint, not a raw local server.

let client: ReturnType<typeof neon> | null = null;

// Create the client lazily on first use. Deferring this (rather than building
// it at import time) keeps SvelteKit's build-time module analysis from
// requiring DATABASE_URL, which is only guaranteed to exist at runtime.
export function getSql(): ReturnType<typeof neon> {
  if (!client) {
    if (!env.DATABASE_URL) {
      throw new Error('DATABASE_URL is not set (see .env.example)');
    }
    client = neon(env.DATABASE_URL);
  }
  return client;
}
