import retry from 'async-retry';
import { kysely } from '../db';

export async function processPaymentWebhook(eventId: string, userId: string) {
  try {
    return await retry(
      async (bail) => {
        try {
          return await kysely.transaction().execute(async (trx) => {
            // @strip-target: intermediate-webhook-idempotency
            // Flawless version: Use the PRIMARY KEY unique constraint to prevent duplicates
            await trx
              .insertInto('processed_webhooks')
              .values({
                event_id: eventId,
                processed_at: new Date().toISOString(),
              })
              .execute();
            // @strip-end

            // Process logic: Award points for successful payment
            await trx
              .updateTable('users')
              .set((eb) => ({
                loyalty_points: eb('loyalty_points', '+', 100),
              }))
              .where('id', '=', userId)
              .execute();

            return { success: true };
          });
        } catch (error: any) {
          // If it's a unique constraint violation, don't retry, just bail
          if (error.code === 'SQLITE_CONSTRAINT_PRIMARYKEY' || error.code === 'SQLITE_CONSTRAINT') {
            bail(error);
            return;
          }
          // Only retry if it's a busy error
          if (error.code === 'SQLITE_BUSY') {
            throw error;
          }
          // For other errors, bail
          bail(error);
        }
      },
      {
        retries: 3,
        minTimeout: 100,
        maxTimeout: 1000,
      }
    );
  } catch (error: any) {
    // Check if it's a unique constraint violation (SQLITE_CONSTRAINT_PRIMARYKEY)
    if (error.code === 'SQLITE_CONSTRAINT_PRIMARYKEY' || error.code === 'SQLITE_CONSTRAINT') {
      return { success: true, duplicate: true };
    }
    throw error;
  }
}
