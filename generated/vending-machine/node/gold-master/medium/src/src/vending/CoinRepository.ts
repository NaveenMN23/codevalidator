import db from '../db';

export class CoinRepository {
  getAllCoins() {
    return db.prepare('SELECT * FROM coins ORDER BY denomination DESC').all();
  }

  updateCoinQuantity(denomination: number, quantity: number) {
    db.prepare('UPDATE coins SET quantity = ? WHERE denomination = ?').run(quantity, denomination);
  }
}