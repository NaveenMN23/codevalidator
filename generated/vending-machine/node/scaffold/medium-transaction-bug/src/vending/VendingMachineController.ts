import { FastifyInstance } from 'fastify';
import { VendingMachineService } from './VendingMachineService';

export async function VendingMachineController(fastify: FastifyInstance) {
  const service = new VendingMachineService();

  fastify.post('/vending/purchase', async (request, reply) => {
    try {
      const { productId, amountPaid } = request.body;
      const result = service.processTransaction(productId, amountPaid);
      reply.send(result);
    } catch (error) {
      reply.status(400).send({ error: error.message });
    }
  });
}