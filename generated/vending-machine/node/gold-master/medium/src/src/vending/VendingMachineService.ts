import db from '../db';

export class VendingMachineService {
  /**
   * Process a transaction for purchasing a product.
   * Hint: read the full transaction flow carefully.
   */
  processTransaction(productId: number, amountPaid: number) {
    const product = db.prepare('SELECT * FROM products WHERE id = ?').get(productId);
if (!product || product.quantity <= 0) {
  throw new Error('Product out of stock');
}
if (amountPaid < product.price) {
  throw new Error('Insufficient funds');
}
const change = this.calculateChange(amountPaid - product.price);
db.prepare('UPDATE products SET quantity = quantity - 1 WHERE id = ?').run(productId);
for (const { denomination, count } of change) {
  db.prepare('UPDATE coins SET quantity = quantity - ? WHERE denomination = ?').run(count, denomination);
}
db.prepare('INSERT INTO transactions (product_id, amount_paid, change_given, status) VALUES (?, ?, ?, ?)')
  .run(productId, amountPaid, JSON.stringify(change), 'completed');
return { product: product.name, change };
}

  calculateChange(amount: number) {
    const coins = db.prepare('SELECT * FROM coins ORDER BY denomination DESC').all();
    let remaining = amount;
    const change = [];
    for (const coin of coins) {
      let count = Math.min(Math.floor(remaining / coin.denomination), coin.quantity);
      if (count > 0) {
        change.push({ denomination: coin.denomination, count });
        remaining -= count * coin.denomination;
      }
    }
    if (remaining > 0) {
      throw new Error('Unable to provide exact change');
    }
    return change;
  }
}