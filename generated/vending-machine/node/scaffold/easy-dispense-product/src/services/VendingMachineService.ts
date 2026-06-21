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
    // TODO: implement this function
  }
}
