import { ProductRepository } from '../repositories/ProductRepository';
import { TransactionRepository } from '../repositories/TransactionRepository';
import { OutOfStockException } from '../exceptions/OutOfStockException';
import { InsufficientFundsException } from '../exceptions/InsufficientFundsException';

export class VendingMachineService {
  private productRepo = new ProductRepository();
  private transactionRepo = new TransactionRepository();

  /**
   * Dispense a product from the vending machine.
   * Check product availability, process payment, dispense the product, and return change if necessary.
   * Handle out-of-stock and insufficient funds errors.
   */
  dispenseProduct(productId: number, amountPaid: number): number {
    const product = this.productRepo.findById(productId);
if (!product) throw new Error('Product not found');
if (product.quantity <= 0) throw new OutOfStockException();
if (amountPaid < product.price) throw new InsufficientFundsException();

// Calculate change
const change = amountPaid - product.price;

// Update product quantity
this.productRepo.updateQuantity(productId, product.quantity - 1);

// Record the transaction
this.transactionRepo.create({
  productId: product.id,
  amountPaid: amountPaid,
  changeGiven: change,
  status: 'completed'
});

return change;
  }
}
