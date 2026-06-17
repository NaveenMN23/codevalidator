import fastify from 'fastify';
import { BookingRequestSchema } from './schemas';
import { bookSeat } from './services/booking';
import { cancelBooking } from './services/cancellation';
import { processPaymentWebhook } from './services/webhook';
import { getShowWithCache } from './services/show';
import { ZodError } from 'zod';

export const buildApp = () => {
  const app = fastify({ logger: false });

  // Advanced Challenge Endpoint
  app.get('/show/:id', async (request, reply) => {
    const { id } = request.params as { id: string };
    const show = await getShowWithCache(id);
    if (!show) return reply.status(404).send({ error: 'Show not found' });
    return reply.send(show);
  });

  // Intermediate Challenge Endpoint (Idempotency)
  app.post('/webhook/payment', async (request, reply) => {
    try {
      const { eventId, userId } = request.body as { eventId: string; userId: string };
      const result = await processPaymentWebhook(eventId, userId);
      return reply.send(result);
    } catch (error) {
      return reply.status(500).send({ error: 'Internal Server Error' });
    }
  });

  // Beginner Challenge Endpoint (Refund Logic)
  app.post('/cancel', async (request, reply) => {
    const { seatId } = request.body as { seatId: string };
    try {
      const result = await cancelBooking(seatId);
      return reply.send(result);
    } catch (error) {
      if (error instanceof Error) {
        return reply.status(400).send({ error: error.message });
      }
      return reply.status(500).send({ error: 'Internal Server Error' });
    }
  });

  // Base Booking Endpoint
  app.post('/book', async (request, reply) => {
    try {
      const { showId, seatNumber } = BookingRequestSchema.parse(request.body);
      const result = await bookSeat(showId, seatNumber);
      return reply.send(result);
    } catch (error) {
      if (error instanceof ZodError) {
        return reply.status(400).send({ error: 'Validation failed', details: error.errors });
      }
      if (error instanceof Error) {
        return reply.status(400).send({ error: error.message });
      }
      return reply.status(500).send({ error: 'Internal Server Error' });
    }
  });

  return app;
};
