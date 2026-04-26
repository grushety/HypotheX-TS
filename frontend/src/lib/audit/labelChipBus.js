// Simple in-process pub/sub for label_chip events.
// OP-041 (backend) publishes chips; AuditLogPanel subscribes.
const subscribers = new Set();

export const labelChipBus = {
  subscribe(handler) {
    subscribers.add(handler);
    return () => subscribers.delete(handler);
  },
  publish(chip) {
    for (const handler of subscribers) {
      handler(chip);
    }
  },
};
