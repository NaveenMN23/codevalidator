import { kysely } from '../db';

export async function cancelBooking(seatId: string) {
  return await kysely.transaction().execute(async (trx) => {
    // Fetch seat and show details
    const data = await trx
      .selectFrom('seats')
      .innerJoin('shows', 'shows.id', 'seats.show_id')
      .select(['seats.id', 'seats.is_booked', 'seats.user_id', 'shows.start_time'])
      .where('seats.id', '=', seatId)
      .executeTakeFirst();

    if (!data) throw new Error('Booking not found');
    if (data.is_booked === 0) throw new Error('Seat is not booked');

    // @strip-target: beginner-broken-refund
    // Validation: Cannot cancel if movie already started
    const startTime = new Date(data.start_time).getTime();
    if (Date.now() > startTime) {
      throw new Error('Cannot cancel after movie has started');
    }
    // @strip-end

    // @strip-target: beginner-broken-refund
    // Release seat
    await trx
      .updateTable('seats')
      .set({ is_booked: 0, user_id: null })
      .where('id', '=', seatId)
      .execute();
    // @strip-end

    // Refund loyalty points (Simplified business logic)
    if (data.user_id) {
      await trx
        .updateTable('users')
        .set((eb) => ({
          loyalty_points: eb('loyalty_points', '+', 10),
        }))
        .where('id', '=', data.user_id)
        .execute();
    }

    return { success: true };
  });
}
