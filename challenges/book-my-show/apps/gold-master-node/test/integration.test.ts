import { describe, it, before as beforeAll, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { buildApp } from '../src/app';
import { initDb, kysely } from '../src/db';
import { randomUUID } from 'crypto';

/**
 * PUBLIC TESTS
 * These tests are visible to the candidate and serve as basic validation.
 * Hidden tests on the server will perform more exhaustive edge-case checks.
 */
describe('BookMyShow Basic Validation', () => {
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

  it('should book an available seat successfully', async () => {
    const movieId = randomUUID();
    const showId = randomUUID();
    const seatNumber = 'A1';

    await kysely.insertInto('movies').values({ id: movieId, title: 'Inception' }).execute();
    await kysely.insertInto('shows').values({ id: showId, movie_id: movieId, start_time: '2026-06-17T20:00:00Z' }).execute();
    await kysely.insertInto('seats').values({ id: randomUUID(), show_id: showId, seat_number: seatNumber, is_booked: 0 }).execute();

    const response = await app.inject({
      method: 'POST',
      url: '/book',
      payload: { showId, seatNumber },
    });

    assert.strictEqual(response.statusCode, 200);
    const body = JSON.parse(response.payload);
    assert.strictEqual(body.success, true);
  });

  it('should process a payment webhook successfully', async () => {
    const userId = randomUUID();
    const eventId = randomUUID();
    await kysely.insertInto('users').values({ id: userId, name: 'Candidate', loyalty_points: 0 }).execute();

    const response = await app.inject({
      method: 'POST',
      url: '/webhook/payment',
      payload: { eventId, userId },
    });

    assert.strictEqual(response.statusCode, 200);
  });
});
