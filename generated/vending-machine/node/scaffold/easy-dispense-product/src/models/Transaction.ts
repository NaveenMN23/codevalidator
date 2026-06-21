export class Transaction {
  constructor(
    public id: number,
    public productId: number,
    public amountPaid: number,
    public changeGiven: number,
    public status: string
  ) {}
}
