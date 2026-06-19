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

  describe('Layer 3: Strict Webhook Idempotency', () => {
    it('should handle interleaved duplicate webhooks', async () => {
      const userId = randomUUID();
      const eventId = randomUUID();
      await kysely.insertInto('users').values({ id: userId, name: 'Idempotency Pro', loyalty_points: 0 }).execute();

      // Launch 10 identical webhook calls simultaneously
      const requests = Array.from({ length: 10 }).map(() =>
        app.inject({
          method: 'POST',
          url: '/webhook/payment',
          payload: { eventId, userId },
        })
      );

      const responses = await Promise.all(requests);
      responses.forEach((r, i) => assert.strictEqual(r.statusCode, 200, `POST /webhook/payment call #${i + 1} should succeed. Expected: 200, Got: ${r.statusCode}`));

      const user = await kysely.selectFrom('users').selectAll().where('id', '=', userId).executeTakeFirst();
      assert.strictEqual(user?.loyalty_points, 100, `10 duplicate webhooks for the same eventId must award loyalty points exactly once (+100 pts). Expected: 100, Got: ${user?.loyalty_points}`);
    });
  });
});
