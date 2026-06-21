package com.challenge.dtos;

import lombok.Data;

@Data
public class ProductDTO {
    private int id;
    private String name;
    private double price;
    private int quantity;

    public ProductDTO(int id, String name, double price, int quantity) {
        this.id = id;
        this.name = name;
        this.price = price;
        this.quantity = quantity;
    }
}
