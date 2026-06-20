import { kysely } from '../db';

export async function bookSeat(showId: string, seatNumber: string) {
  return await kysely.transaction().execute(async (trx) => {
    // Check if the seat is already booked
    const seat = await trx
      .selectFrom('seats')
      .select(['id', 'is_booked'])
      .where('show_id', '=', showId)
      .where('seat_number', '=', seatNumber)
      .executeTakeFirst();

    if (!seat) {
      throw new Error('Seat not found');
    }

    // @strip-target: intermediate-race-condition
    if (seat.is_booked === 1) {
      throw new Error('Seat already booked');
    }
    // @strip-end

    // Atomic update: only set is_booked to 1 if it is currently 0
    const result = await trx
      .updateTable('seats')
      .set({ is_booked: 1 })
      .where('id', '=', seat.id)
      .where('is_booked', '=', 0)
      .executeTakeFirst();

    if (Number(result.numUpdatedRows) === 0) {
      throw new Error('Seat already booked');
    }

    return { success: true, seatId: seat.id };
  });
}
