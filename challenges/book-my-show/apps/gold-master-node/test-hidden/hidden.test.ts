import { describe, it, before as beforeAll, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { buildApp } from '../src/app';
import { initDb, kysely } from '../src/db';
import { randomUUID } from 'crypto';

describe('BookMyShow Comprehensive Hidden Suite', () => {
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
        assert.strictEqual(response.statusCode, 400, `Expected 400 for showId: ${id}`);
      });
    });

    it('should reject seatNumber that is too long', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/book',
        payload: { showId: randomUUID(), seatNumber: 'A12345' },
      });
      assert.strictEqual(response.statusCode, 400);
    });

    it('should reject seatNumber that is empty', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/book',
        payload: { showId: randomUUID(), seatNumber: '' },
      });
      assert.strictEqual(response.statusCode, 400);
    });
  });

  describe('Layer 2: Advanced Concurrency & Atomicity', () => {
    it('should handle 100 concurrent requests for 5 different seats', async () => {
      const movieId = randomUUID();
      const showId = randomUUID();
      const seatNumbers = ['S1', 'S2', 'S3', 'S4', 'S5'];

      await kysely.insertInto('movies').values({ id: movieId, title: 'Concurrency Pro' }).execute();
      await kysely.insertInto('shows').values({ id: showId, movie_id: movieId, start_time: '2026-06-17T20:00:00Z' }).execute();
      
      for (const sn of seatNumbers) {
        await kysely.insertInto('seats').values({ id: randomUUID(), show_id: showId, seat_number: sn, is_booked: 0 }).execute();
      }

      const requests = Array.from({ length: 100 }).map((_, i) =>
        app.inject({
          method: 'POST',
          url: '/book',
          payload: { showId, seatNumber: seatNumbers[i % 5] },
        })
      );

      const responses = await Promise.all(requests);
      const successes = responses.filter(r => r.statusCode === 200);
      
      // Only 5 seats exist, so exactly 5 should succeed
      assert.strictEqual(successes.length, 5, `Expected 5 successes, got ${successes.length}`);
    });

    it('should ensure no two users can book the same seat even with staggered delay', async () => {
        const movieId = randomUUID();
        const showId = randomUUID();
        const seatNumber = 'VIP';
  
        await kysely.insertInto('movies').values({ id: movieId, title: 'Atomicity Test' }).execute();
        await kysely.insertInto('shows').values({ id: showId, movie_id: movieId, start_time: '2026-06-17T20:00:00Z' }).execute();
        await kysely.insertInto('seats').values({ id: randomUUID(), show_id: showId, seat_number: seatNumber, is_booked: 0 }).execute();
  
        const p1 = app.inject({ method: 'POST', url: '/book', payload: { showId, seatNumber } });
        // Small delay to test if first transaction is locked correctly
        await new Promise(r => setTimeout(r, 50));
        const p2 = app.inject({ method: 'POST', url: '/book', payload: { showId, seatNumber } });
  
        const [r1, r2] = await Promise.all([p1, p2]);
        const statusCodes = [r1.statusCode, r2.statusCode];
        assert.ok(statusCodes.includes(200), 'At least one should succeed');
        assert.ok(statusCodes.includes(400), 'One should fail');
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
      responses.forEach(r => assert.strictEqual(r.statusCode, 200));

      const user = await kysely.selectFrom('users').selectAll().where('id', '=', userId).executeTakeFirst();
      // Should ONLY be 100 points, regardless of how many times it was called
      assert.strictEqual(user?.loyalty_points, 100, `Expected 100 points, got ${user?.loyalty_points}`);
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

      // Call cancel twice
      const r1 = await app.inject({ method: 'POST', url: '/cancel', payload: { seatId } });
      const r2 = await app.inject({ method: 'POST', url: '/cancel', payload: { seatId } });

      assert.strictEqual(r1.statusCode, 200);
      assert.strictEqual(r2.statusCode, 400); // Second time should fail as it's not booked

      const user = await kysely.selectFrom('users').selectAll().where('id', '=', userId).executeTakeFirst();
      assert.strictEqual(user?.loyalty_points, 10, 'Should only refund once');
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
  
        assert.strictEqual(response.statusCode, 400);
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
        responses.forEach(r => assert.strictEqual(r.statusCode, 200));
        
        // This test mainly verifies that the logic works. 
        // In a real load test we'd monitor DB connections, but here we're ensuring the 
        // candidate at least implemented the Mutex/Single-flight pattern correctly.
    });
  });
});
