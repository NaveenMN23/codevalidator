package com.platform.calculator;

public class Calculator {

    public int divide(int a, int b) {
        return a / b; // BUG: throws raw ArithmeticException on b == 0
    }
}
