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
  return await mutex.runExclusive(async () => {
    // Re-check cache after acquiring lock (Double-checked locking)
    const reCheck = cache.get(cacheKey);
    if (reCheck && reCheck.expiresAt > now) {
      return reCheck.data;
    }
  // @strip-end

    const show = await kysely
      .selectFrom('shows')
      .selectAll()
      .where('id', '=', showId)
      .executeTakeFirst();

    if (show) {
      cache.set(cacheKey, { data: show, expiresAt: Date.now() + 5000 });
    }

    return show;

  // @strip-target: advanced-cache-stampede
  });
  // @strip-end
}
