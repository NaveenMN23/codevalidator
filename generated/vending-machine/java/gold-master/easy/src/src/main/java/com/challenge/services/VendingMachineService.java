package com.challenge.services;

import com.challenge.dtos.ProductDTO;
import com.challenge.exceptions.InsufficientFundsException;
import com.challenge.exceptions.OutOfStockException;
import com.challenge.models.Product;
import com.challenge.repositories.ProductRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class VendingMachineService {

    @Autowired
    private ProductRepository productRepository;

    /**
     * Dispense a product from the vending machine.
     * 1. Select the product by ID
     * 2. Check if the product is in stock
     * 3. Accept payment and check if sufficient
     * 4. Update product stock
     * 5. Calculate and return change
     * 6. Handle exceptions for insufficient funds and out-of-stock
     */
    public void dispenseProduct(ProductDTO productDTO) {
        Product product = productRepository.findById(productDTO.getProductId())
    .orElseThrow(() -> new OutOfStockException("Product not found"));

if (product.getQuantity() <= 0) {
    throw new OutOfStockException("Product is out of stock");
}

if (productDTO.getAmountPaid() < product.getPrice()) {
    throw new InsufficientFundsException("Insufficient funds");
}

product.setQuantity(product.getQuantity() - 1);
productRepository.save(product);

// Calculate change
// Assuming change is simply the difference
// In a real scenario, you would need to calculate the change using available denominations
// and update the cash repository accordingly

double change = productDTO.getAmountPaid() - product.getPrice();

// Return change (this could be logged, returned, or handled as needed)
System.out.println("Change to return: " + change);
    }

    // Example of a fully implemented method
    public void restockProduct(int productId, int quantity) {
        Product product = productRepository.findById(productId).orElseThrow(() -> new RuntimeException("Product not found"));
        product.setQuantity(product.getQuantity() + quantity);
        productRepository.save(product);
    }
}
