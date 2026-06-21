import { FastifyInstance } from 'fastify';
import { VendingMachineService } from '../services/VendingMachineService';

export async function VendingMachineController(fastify: FastifyInstance) {
  const service = new VendingMachineService();

  fastify.post('/dispense', async (request, reply) => {
    const { productId, amountPaid } = request.body;
    try {
      const change = service.dispenseProduct(productId, amountPaid);
      reply.send({ success: true, change });
    } catch (error) {
      if (error instanceof Error) {
        reply.status(400).send({ success: false, message: error.message });
      }
    }
  });
}
