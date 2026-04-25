export const TIER_0_OPS = [
  { op_name: 'edit_boundary', label: 'Edit Boundary', icon: '⇔', tier: 0 },
  { op_name: 'split',         label: 'Split',         icon: '⌿', tier: 0 },
  { op_name: 'merge',         label: 'Merge',         icon: '⊕', tier: 0 },
];

export const TIER_1_OPS = [
  { op_name: 'scale',                label: 'Scale',           icon: '↕', tier: 1 },
  { op_name: 'offset',               label: 'Offset',          icon: '↑', tier: 1 },
  { op_name: 'mute_zero',            label: 'Mute Zero',       icon: '∅', tier: 1 },
  { op_name: 'time_shift',           label: 'Time Shift',      icon: '→', tier: 1 },
  { op_name: 'reverse_time',         label: 'Reverse',         icon: '⇄', tier: 1 },
  { op_name: 'resample',             label: 'Resample',        icon: '≈', tier: 1 },
  { op_name: 'suppress',             label: 'Suppress',        icon: '⊘', tier: 1 },
  { op_name: 'replace_from_library', label: 'Replace',         icon: '⊞', tier: 1 },
  { op_name: 'add_uncertainty',      label: 'Add Uncertainty', icon: '±', tier: 1 },
];

export const TIER_2_OPS = {
  plateau: [
    { op_name: 'plateau_flatten',       label: 'Flatten',       tier: 2 },
    { op_name: 'plateau_add_noise',     label: 'Add Noise',     tier: 2 },
    { op_name: 'plateau_scale',         label: 'Scale Level',   tier: 2 },
    { op_name: 'plateau_remove_drift',  label: 'Remove Drift',  tier: 2 },
    { op_name: 'plateau_add_seasonal',  label: 'Add Seasonal',  tier: 2 },
  ],
  trend: [
    { op_name: 'trend_change_slope',    label: 'Change Slope',   tier: 2 },
    { op_name: 'trend_reverse',         label: 'Reverse Trend',  tier: 2 },
    { op_name: 'trend_scale',           label: 'Scale',          tier: 2 },
    { op_name: 'trend_add_noise',       label: 'Add Noise',      tier: 2 },
    { op_name: 'trend_detrend',         label: 'Detrend',        tier: 2 },
    { op_name: 'trend_fit_piecewise',   label: 'Fit Piecewise',  tier: 2 },
  ],
  step: [
    { op_name: 'step_adjust_height',    label: 'Adjust Height',  tier: 2 },
    { op_name: 'step_smooth',           label: 'Smooth Step',    tier: 2 },
    { op_name: 'step_scale',            label: 'Scale',          tier: 2 },
    { op_name: 'step_add_noise',        label: 'Add Noise',      tier: 2 },
    { op_name: 'step_remove',           label: 'Remove Step',    tier: 2 },
  ],
  spike: [
    { op_name: 'spike_scale',           label: 'Scale Spike',    tier: 2 },
    { op_name: 'spike_widen',           label: 'Widen',          tier: 2 },
    { op_name: 'spike_narrow',          label: 'Narrow',         tier: 2 },
    { op_name: 'spike_remove',          label: 'Remove Spike',   tier: 2 },
    { op_name: 'spike_add',             label: 'Add Spike',      tier: 2 },
  ],
  cycle: [
    { op_name: 'cycle_scale_amplitude', label: 'Scale Amplitude',    tier: 2 },
    { op_name: 'cycle_shift_phase',     label: 'Shift Phase',        tier: 2 },
    { op_name: 'cycle_change_frequency',label: 'Change Frequency',   tier: 2 },
    { op_name: 'cycle_add_harmonics',   label: 'Add Harmonics',      tier: 2 },
    { op_name: 'cycle_remove_harmonics',label: 'Remove Harmonics',   tier: 2 },
    { op_name: 'cycle_damp',            label: 'Damp',               tier: 2 },
    { op_name: 'cycle_amplify',         label: 'Amplify',            tier: 2 },
  ],
  transient: [
    { op_name: 'transient_scale',           label: 'Scale',           tier: 2 },
    { op_name: 'transient_shift_onset',     label: 'Shift Onset',     tier: 2 },
    { op_name: 'transient_change_duration', label: 'Change Duration', tier: 2 },
    { op_name: 'transient_smooth_onset',    label: 'Smooth Onset',    tier: 2 },
    { op_name: 'transient_sharpen_onset',   label: 'Sharpen Onset',   tier: 2 },
  ],
  noise: [
    { op_name: 'noise_rescale',             label: 'Rescale',              tier: 2 },
    { op_name: 'noise_filter',              label: 'Filter',               tier: 2 },
    { op_name: 'noise_change_distribution', label: 'Change Distribution',  tier: 2 },
    { op_name: 'noise_add_periodic',        label: 'Add Periodic',         tier: 2 },
    { op_name: 'noise_denoise',             label: 'Denoise',              tier: 2 },
  ],
};

export const TIER_3_OPS = [
  { op_name: 'decompose',             label: 'Decompose',            tier: 3 },
  { op_name: 'align_warp',            label: 'Align Warp',           tier: 3, requiresMultiSelect: true },
  { op_name: 'enforce_conservation',  label: 'Enforce Conservation', tier: 3 },
  { op_name: 'aggregate',             label: 'Aggregate',            tier: 3 },
];

export const TIER_LABELS = [
  'Tier 0: structural',
  'Tier 1: basic atoms',
  'Tier 2: shape-specific',
  'Tier 3: composite',
];
