export class InsufficientFundsException extends Error {
  constructor() {
    super('Insufficient funds provided');
  }
}
