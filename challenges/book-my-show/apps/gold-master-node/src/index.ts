import { buildApp } from './app';
import { initDb } from './db';

const start = async () => {
  try {
    await initDb();
    const app = buildApp();
    await app.listen({ port: 3000, host: '0.0.0.0' });
    console.log('Gold Master Server running on http://localhost:3000');
  } catch (err) {
    console.error(err);
    process.exit(1);
  }
};

start();
