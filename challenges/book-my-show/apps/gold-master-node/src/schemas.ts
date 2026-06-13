import { z } from 'zod';

export const BookingRequestSchema = z.object({
  showId: z.string().uuid(),
  seatNumber: z.string().min(1).max(5), // e.g., "A1", "B12"
});

export type BookingRequest = z.infer<typeof BookingRequestSchema>;
