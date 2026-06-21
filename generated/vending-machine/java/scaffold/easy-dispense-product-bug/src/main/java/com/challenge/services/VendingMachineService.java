package com.challenge.services;

import com.challenge.dtos.ProductDTO;
import com.challenge.exceptions.InsufficientFundsException;
import com.challenge.exceptions.OutOfStockException;
import com.challenge.models.Product;
import com.challenge.repositories.ProductRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class VendingMachineService {

    @Autowired
    private ProductRepository productRepository;

    public List<ProductDTO> getAvailableProducts() {
        return productRepository.findAll().stream()
                .map(product -> new ProductDTO(product.getId(), product.getName(), product.getPrice(), product.getQuantity()))
                .collect(Collectors.toList());
    }

    /**
     * Dispense a product if the payment is sufficient and the product is in stock.
     * Hint: read the full dispense flow carefully.
     */
    @Transactional
    public void dispenseProduct(int productId, double amountPaid) throws InsufficientFundsException, OutOfStockException {
        // DEBUG_SCENARIO: easy-dispense-product-bug
        Product product = productRepository.findById(productId)
                .orElseThrow(() -> new OutOfStockException("Product not found."));

        if (product.getQuantity() <= 0) {
            throw new OutOfStockException("Product is out of stock.");
        }

        if (amountPaid < product.getPrice()) {
            throw new InsufficientFundsException("Insufficient funds.");
        }

        // BUG: product.setQuantity(product.getQuantity() - 1) and productRepository.save(product) are missing — intentionally broken
    }

    public void restockProduct(int productId, int quantity) {
        Product product = productRepository.findById(productId)
                .orElseThrow(() -> new RuntimeException("Product not found."));
        product.setQuantity(product.getQuantity() + quantity);
        productRepository.save(product);
    }

    public double collectMoney() {
        // Assume this method collects all money from the machine
        return 0.0;
    }
}
