import { Mutex } from 'async-mutex';
import { kysely } from '../db';

const cache = new Map<string, { data: any; expiresAt: number }>();
const mutex = new Mutex();

export async function getShowWithCache(showId: string) {
  const cacheKey = `show:${showId}`;
  const now = Date.now();

  // Check cache
  const cached = cache.get(cacheKey);
  if (cached && cached.expiresAt > now) {
    return cached.data;
  }

  // @strip-target: advanced-cache-stampede
  // Flawless version: Use a Mutex (Single-flight) to ensure only one request 
  // hits the DB when the cache is empty/expired.
  return await mutex.runExclusive(async () => {
    // Re-check cache after acquiring lock (Double-checked locking)
    const reCheck = cache.get(cacheKey);
    if (reCheck && reCheck.expiresAt > now) {
      return reCheck.data;
    }
    // @strip-end

    // Simulate heavy DB load
    // In a real advanced challenge, this would be a complex query
    // or we'd artificially slow it down to show the stampede effect.
    const show = await kysely
      .selectFrom('shows')
      .selectAll()
      .where('id', '=', showId)
      .executeTakeFirst();

    if (show) {
      // Cache for 5 seconds
      cache.set(cacheKey, { data: show, expiresAt: Date.now() + 5000 });
    }

    return show;
  });
}
