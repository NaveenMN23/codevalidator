package com.challenge.controllers;

import com.challenge.dtos.ProductDTO;
import com.challenge.exceptions.InsufficientFundsException;
import com.challenge.exceptions.OutOfStockException;
import com.challenge.services.VendingMachineService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/vending-machine")
public class VendingMachineController {

    @Autowired
    private VendingMachineService vendingMachineService;

    @GetMapping("/products")
    public List<ProductDTO> getAvailableProducts() {
        return vendingMachineService.getAvailableProducts();
    }

    @PostMapping("/dispense")
    public String dispenseProduct(@RequestParam int productId, @RequestParam double amountPaid) {
        try {
            vendingMachineService.dispenseProduct(productId, amountPaid);
            return "Product dispensed successfully.";
        } catch (InsufficientFundsException | OutOfStockException e) {
            return e.getMessage();
        }
    }

    @PostMapping("/restock")
    public String restockProduct(@RequestParam int productId, @RequestParam int quantity) {
        vendingMachineService.restockProduct(productId, quantity);
        return "Product restocked successfully.";
    }

    @GetMapping("/collect-money")
    public double collectMoney() {
        return vendingMachineService.collectMoney();
    }
}
