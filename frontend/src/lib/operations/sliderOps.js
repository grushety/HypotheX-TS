/**
 * Slider-op registry (UI-016).
 *
 * Maps op_names that share a continuous α (scale-style ops with an
 * amplify ↔ dampen disambiguation) to a slider configuration.  Two
 * op_names mapping to the same `groupId` collapse into one slider
 * control on the palette (e.g. cycle_amplify + cycle_damp → one
 * cycle-amplitude slider).
 *
 * `commitOpName` is the backend op invoked when the slider commits.
 * For amplify/dampen pairs the op_name encodes "amplify with sign-
 * disambiguated α", so a single op handles the whole continuum.
 */

export const SLIDER_OPS = {
  cycle_amplify: {
    groupId: 'cycle_amplitude',
    mode: 'bidirectional',
    label: 'Amplitude',
    commitOpName: 'amplify_amplitude',
    paramKey: 'alpha',
  },
  cycle_damp: {
    groupId: 'cycle_amplitude',
    mode: 'bidirectional',
    label: 'Amplitude',
    commitOpName: 'amplify_amplitude',
    paramKey: 'alpha',
  },
  transient_scale: {
    groupId: 'transient_amplitude',
    mode: 'bidirectional',
    label: 'Amplitude',
    commitOpName: 'transient_scale',
    paramKey: 'alpha',
  },
  spike_scale: {
    groupId: 'spike_amplitude',
    mode: 'amplify-only',
    label: 'Amplitude',
    commitOpName: 'spike_scale',
    paramKey: 'alpha',
  },
  noise_rescale: {
    groupId: 'noise_amplitude',
    mode: 'bidirectional',
    label: 'Amplitude',
    commitOpName: 'noise_rescale',
    paramKey: 'alpha',
  },
};

/** Return the slider config for an op_name, or null. */
export function sliderConfigFor(opName) {
  return SLIDER_OPS[opName] ?? null;
}

/**
 * Group a tier-2 buttons array into a list of mixed controls:
 *   [{kind: 'button', button}, {kind: 'slider', slider, members}, ...]
 *
 * Buttons with no slider config become `{kind: 'button'}` entries.
 * Buttons whose `op_name` is in SLIDER_OPS are merged by `groupId`;
 * the slider is enabled when ANY of its member buttons is enabled,
 * loading when ANY member is loading, and the disabledTooltip falls
 * back to the first member's tooltip.  Order is preserved by the
 * first occurrence of each group / button.
 */
export function groupTier2Controls(buttons) {
  const out = [];
  const groupIndex = new Map();

  for (const btn of buttons) {
    const cfg = sliderConfigFor(btn.op_name);
    if (!cfg) {
      out.push({ kind: 'button', button: btn });
      continue;
    }

    if (groupIndex.has(cfg.groupId)) {
      const idx = groupIndex.get(cfg.groupId);
      const existing = out[idx];
      existing.members.push(btn);
      existing.slider.enabled = existing.slider.enabled || btn.enabled;
      existing.slider.loading = existing.slider.loading || btn.loading;
      if (existing.slider.disabledTooltip == null && btn.disabledTooltip) {
        existing.slider.disabledTooltip = btn.disabledTooltip;
      }
      continue;
    }

    const sliderControl = {
      kind: 'slider',
      slider: {
        groupId: cfg.groupId,
        label: cfg.label,
        mode: cfg.mode,
        commitOpName: cfg.commitOpName,
        paramKey: cfg.paramKey,
        tier: btn.tier,
        enabled: btn.enabled,
        loading: btn.loading,
        disabledTooltip: btn.disabledTooltip ?? null,
      },
      members: [btn],
    };
    groupIndex.set(cfg.groupId, out.length);
    out.push(sliderControl);
  }

  return out;
}
