export class OutOfStockException extends Error {
  constructor() {
    super('Product is out of stock');
  }
}
