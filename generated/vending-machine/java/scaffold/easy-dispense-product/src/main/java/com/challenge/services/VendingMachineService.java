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
        // TODO: implement this method
    }

    // Example of a fully implemented method
    public void restockProduct(int productId, int quantity) {
        Product product = productRepository.findById(productId).orElseThrow(() -> new RuntimeException("Product not found"));
        product.setQuantity(product.getQuantity() + quantity);
        productRepository.save(product);
    }
}
