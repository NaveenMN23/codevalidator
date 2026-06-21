package com.platform.calculator;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class CalculatorTest {

    private final Calculator calculator = new Calculator();

    @Test
    void dividesTwoNumbers() {
        assertEquals(2, calculator.divide(10, 5));
    }

    @Test
    void divisionByZeroThrowsIllegalArgument() {
        assertThrows(IllegalArgumentException.class, () -> calculator.divide(10, 0));
    }
}
