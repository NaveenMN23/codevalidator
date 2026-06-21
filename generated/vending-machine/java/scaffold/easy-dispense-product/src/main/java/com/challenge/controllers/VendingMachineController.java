package com.challenge.controllers;

import com.challenge.dtos.ProductDTO;
import com.challenge.exceptions.InsufficientFundsException;
import com.challenge.exceptions.OutOfStockException;
import com.challenge.services.VendingMachineService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/vending-machine")
public class VendingMachineController {

    @Autowired
    private VendingMachineService vendingMachineService;

    @PostMapping("/dispense")
    public ResponseEntity<String> dispenseProduct(@RequestBody ProductDTO productDTO) {
        try {
            vendingMachineService.dispenseProduct(productDTO);
            return new ResponseEntity<>("Product dispensed successfully", HttpStatus.OK);
        } catch (InsufficientFundsException | OutOfStockException e) {
            return new ResponseEntity<>(e.getMessage(), HttpStatus.BAD_REQUEST);
        }
    }

    // Example of a fully implemented method
    @GetMapping("/products")
    public ResponseEntity<String> getAvailableProducts() {
        return new ResponseEntity<>("List of available products", HttpStatus.OK);
    }

    @PostMapping("/restock")
    public ResponseEntity<String> restockProducts() {
        return new ResponseEntity<>("Products restocked", HttpStatus.OK);
    }

    @PostMapping("/collect-money")
    public ResponseEntity<String> collectMoney() {
        return new ResponseEntity<>("Money collected", HttpStatus.OK);
    }
}
