import db from '../db';

export class TransactionRepository {
  createTransaction(productId: number, amountPaid: number, changeGiven: number, status: string) {
    db.prepare('INSERT INTO transactions (product_id, amount_paid, change_given, status) VALUES (?, ?, ?, ?)')
      .run(productId, amountPaid, changeGiven, status);
  }
}