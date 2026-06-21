import db from '../db';

export class ProductRepository {
  getProductById(productId: number) {
    return db.prepare('SELECT * FROM products WHERE id = ?').get(productId);
  }

  updateProductQuantity(productId: number, quantity: number) {
    db.prepare('UPDATE products SET quantity = ? WHERE id = ?').run(quantity, productId);
  }
}