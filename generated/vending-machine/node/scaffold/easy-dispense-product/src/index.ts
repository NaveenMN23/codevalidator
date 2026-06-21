import Fastify from 'fastify';
import { VendingMachineController } from './controllers/VendingMachineController';

const app = Fastify();

app.register(VendingMachineController, { prefix: '/vending' });

app.listen(3000, (err, address) => {
  if (err) {
    console.error(err);
    process.exit(1);
  }
  console.log(`Server listening at ${address}`);
});
