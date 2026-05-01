/**
 * HTTP client for the semantic-pack routes (UI-014).
 */

async function readJsonResponse(response, label) {
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`${label} response was not valid JSON.`);
  }
  if (!response.ok) {
    const message =
      payload && typeof payload.error === 'string'
        ? payload.error
        : `${label} request failed with status ${response.status}.`;
    throw new Error(message);
  }
  if (!payload || typeof payload !== 'object') {
    throw new Error(`${label} response must be an object.`);
  }
  return payload;
}

export async function fetchSemanticPacks(fetchImpl = fetch) {
  const response = await fetchImpl('/api/semantic-packs');
  const payload = await readJsonResponse(response, 'Semantic packs');
  if (!Array.isArray(payload.packs)) {
    throw new Error('Semantic packs response must include a packs array.');
  }
  return payload;
}

export async function labelSemanticSegments(
  { packName = null, customYaml = null, values = [], segments = [], context = {} },
  fetchImpl = fetch,
) {
  if (!packName && !customYaml) {
    throw new Error('labelSemanticSegments requires packName or customYaml.');
  }
  const body = {
    values,
    segments,
    context,
  };
  if (packName) body.pack_name = packName;
  if (customYaml) body.custom_yaml = customYaml;

  const response = await fetchImpl('/api/semantic-packs/label-segments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await readJsonResponse(response, 'Label segments');
  if (!Array.isArray(payload.results)) {
    throw new Error('Label segments response must include a results array.');
  }
  return payload;
}

export async function validateSemanticPackYaml(yamlText, fetchImpl = fetch) {
  const response = await fetchImpl('/api/semantic-packs/validate-yaml', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ yaml: yamlText }),
  });
  const payload = await readJsonResponse(response, 'Validate YAML');
  if (typeof payload.ok !== 'boolean') {
    throw new Error('Validate YAML response must include an ok boolean.');
  }
  return payload;
}
