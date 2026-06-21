# Vending Machine: Dispense Product

## Problem Statement
The vending machine is designed to support multiple products with different prices and quantities. It accepts coins and notes of different denominations, dispenses the selected product, and returns change if necessary. The machine keeps track of available products and their quantities, handles multiple transactions concurrently, and ensures data consistency. It also provides an interface for restocking products and collecting money. This feature focuses on dispensing a product, checking availability, accepting payment, and handling exceptions such as insufficient funds or out-of-stock products.

## Requirements
1. Implement the `dispenseProduct()` method to select a product, check availability, accept payment, dispense the product, and return change.
2. The request must contain the product ID and the amount paid (see `ProductDTO`).
3. Ensure that the product is in stock and that the payment is sufficient.
4. Update the product's stock quantity upon successful transaction.
5. Handle exceptions for insufficient funds and out-of-stock products using `InsufficientFundsException` and `OutOfStockException`.

## Instructions
1. Carefully look at `ProductDTO` in `dtos/` for the request structure.
2. Examine the `models/` package to understand the database schema.
3. Implement the `dispenseProduct` method inside `VendingMachineService`.
4. Use `ProductRepository` to interact with the database — query or mutate as needed.
5. You might need to add annotations like `@Service`, `@Autowired`, `@Transactional`, `@Entity` to make the solution work.
6. Handle exceptions using the provided classes in the `exceptions/` package.
7. Carefully examine `VendingMachineController` to understand how the solution will be tested. Your implementation must pass all tests.

## How to Build and Run
1. `./mvnw clean package -DskipTests`
2. `./mvnw spring-boot:run`
3. `./mvnw test`
