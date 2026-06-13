# Gold Master Node App

An example Node.js service used in technical challenges (e.g., the "Book My Show" challenge).

## Tech Stack
- **Framework:** Fastify
- **Database:** SQLite (via Kysely query builder)
- **Validation:** Zod
- **Resilience:** async-retry

## Features
- **Webhook Processing:** Idempotent processing of payment webhooks.
- **Seat Booking:** Transactional booking logic for theater seats.
- **Concurrency Handling:** Implements retries for `SQLITE_BUSY` errors to handle high-concurrency scenarios in a single-file database.

## Development

### Run
```bash
npm install
npm run dev
```

### Test
```bash
npm test
```
