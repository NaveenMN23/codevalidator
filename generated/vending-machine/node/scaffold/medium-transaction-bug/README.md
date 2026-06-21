# Vending Machine: Incorrect Change Calculation

## Problem Statement
The vending machine is designed to handle multiple products with different prices and quantities. It accepts various denominations of coins and notes, dispenses the selected product, and returns change if necessary. The machine tracks available products and their quantities, handles multiple transactions concurrently, and ensures data consistency. It also provides interfaces for restocking products and collecting money. However, there is a bug in the change calculation logic that needs to be fixed.

## Requirements
1. Identify and fix the bug in the `processTransaction` function that causes incorrect change to be returned.
2. Ensure that the change calculation prioritizes higher denominations first.
3. Handle scenarios where exact change cannot be provided.
4. Maintain data consistency across transactions.
5. Ensure that the vending machine can handle concurrent transactions without errors.

## Instructions
Investigate and fix the bug in `processTransaction` inside `src/vending/VendingMachineService.ts`. Read the full feature flow carefully — the function runs without errors but produces incorrect results.

## How to Build and Run
1. `npm install`
2. `npm start`
3. `npm test`