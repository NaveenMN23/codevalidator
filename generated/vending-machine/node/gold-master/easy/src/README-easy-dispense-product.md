# Vending Machine: Dispense Product

## Problem Statement
The vending machine is designed to handle multiple products with varying prices and quantities. It accepts coins and notes of different denominations, dispenses selected products, and returns change if necessary. The machine should also manage product inventory and handle multiple transactions concurrently, ensuring data consistency. This feature focuses on dispensing a product, processing payment, and handling exceptions like out-of-stock products or insufficient funds.

## Requirements
1. Implement the `dispenseProduct` function to check product availability and process payment.
2. Ensure the function deducts the product quantity and calculates the correct change.
3. Handle exceptions for out-of-stock products and insufficient funds.
4. Ensure data consistency during concurrent transactions.
5. Update the transaction status appropriately.

## Instructions
1. Carefully look at the types/interfaces in `src/models/Product.ts` and `src/models/Transaction.ts` for request/response structures.
2. Examine `src/db.ts` to understand the database schema and seed data.
3. Implement the `dispenseProduct` function inside `src/services/VendingMachineService.ts`.
4. Use the existing DB helper calls in `src/repositories/ProductRepository.ts` and `src/repositories/TransactionRepository.ts` to query or mutate data.
5. Return the correct HTTP status codes and response shapes — follow the pattern of existing implemented functions.
6. Handle edge cases as required by the tests.

## How to Build and Run
1. `npm install`
2. `npm start`
3. `npm test`
