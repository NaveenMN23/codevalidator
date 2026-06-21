import db from '../db';
import { Transaction } from '../models/Transaction';

export class TransactionRepository {
  create(transaction: Transaction): void {
    db.prepare('INSERT INTO transactions (product_id, amount_paid, change_given, status) VALUES (?, ?, ?, ?)')
      .run(transaction.productId, transaction.amountPaid, transaction.changeGiven, transaction.status);
  }
}
