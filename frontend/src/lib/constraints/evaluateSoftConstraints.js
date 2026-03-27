import { validateEditableSegments } from "../segments/validateEditableSegments.js";

export const SOFT_CONSTRAINT_STATUS = {
  PASS: "PASS",
  WARN: "WARN",
};

export const SOFT_CONSTRAINT_WARNING_CODES = {
  ADJACENT_SAME_LABEL_SEGMENTS: "ADJACENT_SAME_LABEL_SEGMENTS",
};

export const DEFAULT_SOFT_CONSTRAINT_RULES = ["adjacentSameLabelSegments"];

function createPass(action, warnings = []) {
  return {
    ok: true,
    status: SOFT_CONSTRAINT_STATUS.PASS,
    warnings,
    action,
  };
}

function createWarn(action, warnings) {
  return {
    ok: true,
    status: SOFT_CONSTRAINT_STATUS.WARN,
    warnings,
    action,
  };
}

function createFailure(code, message, action) {
  return {
    ok: false,
    code,
    message,
    action,
  };
}

function evaluateAdjacentSameLabelSegments(nextSegments, action) {
  const warnings = [];

  for (let index = 0; index < nextSegments.length - 1; index += 1) {
    const leftSegment = nextSegments[index];
    const rightSegment = nextSegments[index + 1];

    if (leftSegment.label !== rightSegment.label) {
      continue;
    }

    warnings.push({
      code: SOFT_CONSTRAINT_WARNING_CODES.ADJACENT_SAME_LABEL_SEGMENTS,
      message: `Adjacent ${leftSegment.label} segments may indicate a missed merge opportunity.`,
      constraintId: "adjacentSameLabelSegments",
      actionType: action.type,
      segmentIds: [leftSegment.id, rightSegment.id],
      labels: [leftSegment.label],
      details: {
        label: leftSegment.label,
        boundaryIndex: index,
      },
    });
  }

  return warnings;
}

const SOFT_CONSTRAINT_RULES = {
  adjacentSameLabelSegments: evaluateAdjacentSameLabelSegments,
};

export function evaluateSoftConstraints(previousSegments, nextSegments, action, config = {}) {
  const previousValidation = validateEditableSegments(previousSegments);

  if (!previousValidation.ok) {
    return createFailure(previousValidation.code, previousValidation.message, action);
  }

  const nextValidation = validateEditableSegments(nextSegments);

  if (!nextValidation.ok) {
    return createFailure(nextValidation.code, nextValidation.message, action);
  }

  if (!action || typeof action !== "object" || !action.type) {
    return createFailure(
      "INVALID_ACTION",
      "Soft constraint evaluation requires an action with a type.",
      action,
    );
  }

  const activeRules = config.rules ?? DEFAULT_SOFT_CONSTRAINT_RULES;
  const warnings = activeRules.flatMap((ruleName) => {
    const rule = SOFT_CONSTRAINT_RULES[ruleName];

    if (!rule) {
      return [];
    }

    return rule(nextSegments, action, {
      previousSegments,
      config,
    });
  });

  if (warnings.length === 0) {
    return createPass(action);
  }

  return createWarn(action, warnings);
}

export function evaluateEditSoftConstraints(previousSegments, nextSegments, editRequest, config = {}) {
  return evaluateSoftConstraints(previousSegments, nextSegments, editRequest, config);
}

export function evaluateOperationSoftConstraints(
  previousSegments,
  nextSegments,
  operationRequest,
  config = {},
) {
  return evaluateSoftConstraints(previousSegments, nextSegments, operationRequest, config);
}
