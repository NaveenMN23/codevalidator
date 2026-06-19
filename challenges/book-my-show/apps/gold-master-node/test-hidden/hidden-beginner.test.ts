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

  describe('Layer 4: Complex Cancellation Rules', () => {
    it('should release seat and refund points exactly once for multiple cancel calls', async () => {
      const userId = randomUUID();
      const movieId = randomUUID();
      const showId = randomUUID();
      const seatId = randomUUID();
      const futureTime = new Date(Date.now() + 3600000).toISOString();

      await kysely.insertInto('users').values({ id: userId, name: 'Refund Pro', loyalty_points: 0 }).execute();
      await kysely.insertInto('movies').values({ id: movieId, title: 'Cancellation Pro' }).execute();
      await kysely.insertInto('shows').values({ id: showId, movie_id: movieId, start_time: futureTime }).execute();
      await kysely.insertInto('seats').values({ id: seatId, show_id: showId, seat_number: 'A1', is_booked: 1, user_id: userId }).execute();

      const r1 = await app.inject({ method: 'POST', url: '/cancel', payload: { seatId } });
      const r2 = await app.inject({ method: 'POST', url: '/cancel', payload: { seatId } });

      assert.strictEqual(r1.statusCode, 200, `POST /cancel: first cancellation of a booked seat should succeed. Expected: 200, Got: ${r1.statusCode}`);
      assert.strictEqual(r2.statusCode, 400, `POST /cancel: second cancellation of the same seat (already unbooked) should fail. Expected: 400, Got: ${r2.statusCode}`);

      const user = await kysely.selectFrom('users').selectAll().where('id', '=', userId).executeTakeFirst();
      assert.strictEqual(user?.loyalty_points, 10, `Loyalty points must be refunded exactly once (+10 pts). Expected: 10, Got: ${user?.loyalty_points}`);
    });

    it('should block cancellation 1 second after movie start', async () => {
      const userId = randomUUID();
      const showId = randomUUID();
      const seatId = randomUUID();
      const oneSecondAgo = new Date(Date.now() - 1000).toISOString();

      await kysely.insertInto('users').values({ id: userId, name: 'Timing Test', loyalty_points: 0 }).execute();
      await kysely.insertInto('shows').values({ id: showId, movie_id: randomUUID(), start_time: oneSecondAgo }).execute();
      await kysely.insertInto('seats').values({ id: seatId, show_id: showId, seat_number: 'B1', is_booked: 1, user_id: userId }).execute();

      const response = await app.inject({
        method: 'POST',
        url: '/cancel',
        payload: { seatId },
      });

      assert.strictEqual(response.statusCode, 400, `POST /cancel: cancellation 1 second after movie start must be blocked. Expected: 400, Got: ${response.statusCode}`);
    });
  });
});
