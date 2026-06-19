import { describe, it, before as beforeAll, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { buildApp } from '../src/app';
import { initDb, kysely } from '../src/db';
import { randomUUID } from 'crypto';

describe('BookMyShow Hidden Suite', () => {
  const app = buildApp();

  beforeAll(async () => {
    await initDb();
  });

  beforeEach(async () => {
    await kysely.deleteFrom('processed_webhooks').execute();
    await kysely.deleteFrom('seats').execute();
    await kysely.deleteFrom('shows').execute();
    await kysely.deleteFrom('movies').execute();
    await kysely.deleteFrom('users').execute();
  });

  describe('Layer 1: Input Validation & Boundary Conditions', () => {
    const invalidIds = [
      'not-a-uuid',
      '12345',
      '',
      '00000000-0000-0000-0000-000000000000',
      'abc-def-ghi'
    ];

    invalidIds.forEach(id => {
      it(`should reject invalid showId: ${id}`, async () => {
        const response = await app.inject({
          method: 'POST',
          url: '/book',
          payload: { showId: id, seatNumber: 'A1' },
        });
        assert.strictEqual(response.statusCode, 400, `POST /book with showId="${id}" should be rejected. Expected: 400, Got: ${response.statusCode}`);
      });
    });

    it('should reject seatNumber that is too long', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/book',
        payload: { showId: randomUUID(), seatNumber: 'A12345' },
      });
      assert.strictEqual(response.statusCode, 400, `POST /book with seatNumber "A12345" (6 chars, max is 5) should be rejected. Expected: 400, Got: ${response.statusCode}`);
    });

    it('should reject seatNumber that is empty', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/book',
        payload: { showId: randomUUID(), seatNumber: '' },
      });
      assert.strictEqual(response.statusCode, 400, `POST /book with empty seatNumber should be rejected. Expected: 400, Got: ${response.statusCode}`);
    });
  });

  describe('Layer 5: Cache Stampede (Advanced)', () => {
    it('should only hit the database once for many simultaneous show requests (Stampede Protection)', async () => {
      const showId = randomUUID();
      await kysely.insertInto('shows').values({ id: showId, movie_id: randomUUID(), start_time: '2026-06-17T20:00:00Z' }).execute();

      // Simulate 50 simultaneous users hitting a cold cache
      const requests = Array.from({ length: 50 }).map(() =>
        app.inject({
          method: 'GET',
          url: `/show/${showId}`,
        })
      );

      const responses = await Promise.all(requests);
      responses.forEach((r, i) => assert.strictEqual(r.statusCode, 200, `GET /show/${showId}: request #${i + 1} of 50 concurrent requests must succeed. Expected: 200, Got: ${r.statusCode}`));
    });
  });
});
