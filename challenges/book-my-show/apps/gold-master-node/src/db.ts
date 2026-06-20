import Database from 'better-sqlite3';
import { Kysely, SqliteDialect } from 'kysely';

interface UserTable {
  id: string;
  name: string;
  loyalty_points: number;
}

interface MovieTable {
  id: string;
  title: string;
}

interface ShowTable {
  id: string;
  movie_id: string;
  start_time: string; // ISO String
}

interface SeatTable {
  id: string;
  show_id: string;
  seat_number: string;
  is_booked: number; // 0 or 1
  user_id: string | null;
}

interface ProcessedWebhookTable {
  event_id: string;
  processed_at: string;
}

interface DatabaseSchema {
  users: UserTable;
  movies: MovieTable;
  shows: ShowTable;
  seats: SeatTable;
  processed_webhooks: ProcessedWebhookTable;
}

const database = new Database(':memory:');

export const kysely = new Kysely<DatabaseSchema>({
  dialect: new SqliteDialect({ database }),
});

export async function initDb() {
  await kysely.schema
    .createTable('users')
    .ifNotExists()
    .addColumn('id', 'text', (col) => col.primaryKey())
    .addColumn('name', 'text', (col) => col.notNull())
    .addColumn('loyalty_points', 'integer', (col) => col.notNull().defaultTo(0))
    .execute();

  await kysely.schema
    .createTable('movies')
    .ifNotExists()
    .addColumn('id', 'text', (col) => col.primaryKey())
    .addColumn('title', 'text', (col) => col.notNull())
    .execute();

  await kysely.schema
    .createTable('shows')
    .ifNotExists()
    .addColumn('id', 'text', (col) => col.primaryKey())
    .addColumn('movie_id', 'text', (col) => col.notNull())
    .addColumn('start_time', 'text', (col) => col.notNull())
    .execute();

  await kysely.schema
    .createTable('seats')
    .ifNotExists()
    .addColumn('id', 'text', (col) => col.primaryKey())
    .addColumn('show_id', 'text', (col) => col.notNull())
    .addColumn('seat_number', 'text', (col) => col.notNull())
    .addColumn('is_booked', 'integer', (col) => col.notNull().defaultTo(0))
    .addColumn('user_id', 'text')
    .execute();
  
  await kysely.schema
    .createIndex('idx_seats_show_number')
    .on('seats')
    .columns(['show_id', 'seat_number'])
    .ifNotExists()
    .execute();

  await kysely.schema
    .createTable('processed_webhooks')
    .ifNotExists()
    .addColumn('event_id', 'text', (col) => col.primaryKey())
    .addColumn('processed_at', 'text', (col) => col.notNull())
    .execute();
}
