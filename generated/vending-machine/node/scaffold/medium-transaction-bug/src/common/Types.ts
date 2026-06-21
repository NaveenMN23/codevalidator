export interface Product {
  id: number;
  name: string;
  price: number;
  quantity: number;
}

export interface Transaction {
  id: number;
  product_id: number;
  amount_paid: number;
  change_given: number;
  status: string;
}

export interface Coin {
  denomination: number;
  quantity: number;
}