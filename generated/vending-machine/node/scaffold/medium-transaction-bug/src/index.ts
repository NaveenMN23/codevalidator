import Fastify from 'fastify';
import { VendingMachineController } from './vending/VendingMachineController';

const server = Fastify();

server.register(VendingMachineController);

server.listen(3000, (err, address) => {
  if (err) {
    console.error(err);
    process.exit(1);
  }
  console.log(`Server listening at ${address}`);
});