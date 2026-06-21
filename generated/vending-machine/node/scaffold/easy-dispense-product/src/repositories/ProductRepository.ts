import db from '../db';
import { Product } from '../models/Product';

export class ProductRepository {
  findById(productId: number): Product | undefined {
    const row = db.prepare('SELECT * FROM products WHERE id = ?').get(productId);
    return row ? new Product(row.id, row.name, row.price, row.quantity) : undefined;
  }

  updateQuantity(productId: number, quantity: number): void {
    db.prepare('UPDATE products SET quantity = ? WHERE id = ?').run(quantity, productId);
  }
}
