import { describe, it, expect, beforeAll, beforeEach } from 'vitest';
import { buildApp } from '../src/app';
import { initDb, kysely } from '../src/db';
import { randomUUID } from 'crypto';

describe('BookMyShow Gold Master Integration', () => {
  const app = buildApp();

  beforeAll(async () => {
    await initDb();
  });

  beforeEach(async () => {
    // Thorough cleanup
    await kysely.deleteFrom('processed_webhooks').execute();
    await kysely.deleteFrom('seats').execute();
    await kysely.deleteFrom('shows').execute();
    await kysely.deleteFrom('movies').execute();
    await kysely.deleteFrom('users').execute();
  });

  describe('Beginner Scenario: Cancellations & Refunds', () => {
    it('should release seat and refund points when cancelled before start time', async () => {
      const userId = randomUUID();
      const movieId = randomUUID();
      const showId = randomUUID();
      const seatId = randomUUID();
      const futureTime = new Date(Date.now() + 3600000).toISOString();

      await kysely.insertInto('users').values({ id: userId, name: 'User', loyalty_points: 0 }).execute();
      await kysely.insertInto('movies').values({ id: movieId, title: 'Inception' }).execute();
      await kysely.insertInto('shows').values({ id: showId, movie_id: movieId, start_time: futureTime }).execute();
      await kysely.insertInto('seats').values({ id: seatId, show_id: showId, seat_number: 'A1', is_booked: 1, user_id: userId }).execute();

      const response = await app.inject({
        method: 'POST',
        url: '/cancel',
        payload: { seatId },
      });

      expect(response.statusCode).toBe(200);
      const seat = await kysely.selectFrom('seats').selectAll().where('id', '=', seatId).executeTakeFirst();
      expect(seat?.is_booked).toBe(0);
      const user = await kysely.selectFrom('users').selectAll().where('id', '=', userId).executeTakeFirst();
      expect(user?.loyalty_points).toBe(10);
    });

    it('should block cancellation if the movie has already started', async () => {
      const userId = randomUUID();
      const movieId = randomUUID();
      const showId = randomUUID();
      const seatId = randomUUID();
      const pastTime = new Date(Date.now() - 3600000).toISOString();

      await kysely.insertInto('users').values({ id: userId, name: 'User', loyalty_points: 0 }).execute();
      await kysely.insertInto('movies').values({ id: movieId, title: 'Inception' }).execute();
      await kysely.insertInto('shows').values({ id: showId, movie_id: movieId, start_time: pastTime }).execute();
      await kysely.insertInto('seats').values({ id: seatId, show_id: showId, seat_number: 'A1', is_booked: 1, user_id: userId }).execute();

      const response = await app.inject({
        method: 'POST',
        url: '/cancel',
        payload: { seatId },
      });

      expect(response.statusCode).toBe(400);
      expect(JSON.parse(response.payload).error).toBe('Cannot cancel after movie has started');
    });
  });

  describe('Intermediate Scenario: Webhook Idempotency', () => {
    it('should only award points once for duplicate webhooks', async () => {
      const userId = randomUUID();
      const eventId = randomUUID();
      await kysely.insertInto('users').values({ id: userId, name: 'User', loyalty_points: 0 }).execute();

      // First webhook
      const res1 = await app.inject({
        method: 'POST',
        url: '/webhook/payment',
        payload: { eventId, userId },
      });
      expect(res1.statusCode).toBe(200);

      // Duplicate webhook
      const res2 = await app.inject({
        method: 'POST',
        url: '/webhook/payment',
        payload: { eventId, userId },
      });
      expect(res2.statusCode).toBe(200);

      const user = await kysely.selectFrom('users').selectAll().where('id', '=', userId).executeTakeFirst();
      expect(user?.loyalty_points).toBe(100);
    });
  });

  describe('Concurrency & Race Conditions', () => {
    it('should only allow one booking when 10 concurrent requests hit the same seat', async () => {
      const movieId = randomUUID();
      const showId = randomUUID();
      const seatNumber = 'B2';
      
      await kysely.insertInto('movies').values({ id: movieId, title: 'Inception' }).execute();
      await kysely.insertInto('shows').values({ id: showId, movie_id: movieId, start_time: '2026-05-24T20:00:00Z' }).execute();
      await kysely.insertInto('seats').values({ id: randomUUID(), show_id: showId, seat_number: seatNumber, is_booked: 0 }).execute();

      const requests = Array.from({ length: 10 }).map(() => 
        app.inject({
          method: 'POST',
          url: '/book',
          payload: { showId, seatNumber },
        })
      );

      const responses = await Promise.all(requests);
      const successes = responses.filter(r => r.statusCode === 200);
      expect(successes.length).toBe(1);
    });
  });
});
