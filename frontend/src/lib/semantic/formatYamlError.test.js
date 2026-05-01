import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { formatYamlError } from './formatYamlError.js';

describe('formatYamlError', () => {
  it('returns empty string for null/undefined', () => {
    assert.equal(formatYamlError(null), '');
    assert.equal(formatYamlError(undefined), '');
  });

  it('formats yaml-kind errors with line number', () => {
    const out = formatYamlError({
      message: 'mapping values are not allowed here',
      line: 4,
      kind: 'yaml',
    });
    assert.match(out, /YAML error on line 4:/);
    assert.match(out, /mapping values/);
  });

  it('formats schema-kind errors without line number', () => {
    const out = formatYamlError({
      message: "label 'ghost' references unknown detector 'nope'",
      line: null,
      kind: 'schema',
    });
    assert.match(out, /^Schema error:/);
    assert.match(out, /ghost/);
  });

  it('formats yaml errors without a line as just the kind', () => {
    const out = formatYamlError({ message: 'broken', kind: 'yaml' });
    assert.equal(out, 'YAML error: broken');
  });

  it('treats unknown kind as YAML error', () => {
    const out = formatYamlError({ message: 'x', kind: 'something-else' });
    assert.match(out, /^YAML error:/);
  });
});
