# Vending Machine: Product Dispense Bug

## Problem Statement
The vending machine system is designed to handle multiple products with varying prices and quantities. It accepts coins and notes, dispenses selected products, and returns change if necessary. The machine should also manage product inventory and handle concurrent transactions while ensuring data consistency. This specific feature focuses on fixing a bug in the product dispensing functionality.

## Requirements
1. Identify and fix the bug in the `dispenseProduct` method where the product quantity is not decremented after a successful transaction.
2. Ensure that the product quantity is updated correctly in the database after dispensing.
3. Handle exceptions for insufficient funds and out-of-stock products using the provided exception classes.
4. Ensure that the method runs without exceptions and produces the correct results.

## Instructions
Investigate and fix the bug in `VendingMachineService.dispenseProduct()`. Read the full feature flow carefully — the method runs without exceptions but produces incorrect results.

## How to Build and Run
1. `./mvnw clean package -DskipTests`
2. `./mvnw spring-boot:run`
3. `./mvnw test`
