/**
 * Topic-aware in-process pub/sub for validation-metric events (HTS-107).
 *
 * The existing ``labelChipBus`` is topic-less (one event type — the chip),
 * but `GuardrailsSidebar` (VAL-014) expects a ``subscribe(topic, handler)``
 * surface so it can attach one handler per metric topic
 * (``coverage_update`` / ``diversity_update`` / ``validity_update`` /
 * ``cherry_picking_update`` / ``forking_paths_update``).
 *
 * This is the project-wide singleton the sidebar binds to. Future
 * tickets (VAL-010..014 frontend-side metric calculators) will publish
 * to it; today HTS-101's dispatcher publishes a coarse
 * ``validity_update`` summary so the sidebar receives at least one
 * event per Tier-2 op.
 */

function makeBus() {
  const subscribers = new Map(); // topic -> Set<handler>

  function subscribe(topic, handler) {
    if (!subscribers.has(topic)) subscribers.set(topic, new Set());
    subscribers.get(topic).add(handler);
    return () => unsubscribe(topic, handler);
  }

  function unsubscribe(topic, handler) {
    subscribers.get(topic)?.delete(handler);
  }

  function publish(topic, payload) {
    const handlers = subscribers.get(topic);
    if (!handlers) return;
    for (const handler of handlers) {
      try {
        handler(payload);
      } catch {
        /* swallow per-handler errors so one bad handler doesn't break the loop */
      }
    }
  }

  function clear() {
    subscribers.clear();
  }

  return Object.freeze({ subscribe, unsubscribe, publish, clear });
}

export const validationBus = makeBus();

// Exported for tests that want an isolated bus.
export { makeBus };
