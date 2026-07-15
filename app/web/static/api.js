// The only place in the UI that talks to the network. Every screen goes
// through these calls -- there is no business logic on this side of the wire.

async function req(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail;
    try {
      const data = await res.json();
      detail = data.detail;
    } catch {
      detail = await res.text();
    }
    throw new Error(formatDetail(detail) || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return null;
  return res.headers.get('content-type')?.includes('json') ? res.json() : res;
}

// FastAPI returns validation errors as a list of {loc, msg}; flatten them into
// something a human can act on rather than dumping [object Object].
function formatDetail(detail) {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const path = (e.loc || []).filter((p) => p !== 'body').join('.');
        return path ? `${path}: ${e.msg}` : e.msg;
      })
      .join('\n');
  }
  return JSON.stringify(detail);
}

export const api = {
  // recipes -- the definitions
  recipeDefaults: () => req('GET', '/recipes/defaults'),
  listRecipes: () => req('GET', '/recipes').then((d) => d.recipes),
  getRecipe: (id) => req('GET', `/recipes/${id}`),
  createRecipe: (name, recipe) => req('POST', '/recipes', { name, recipe }),
  updateRecipe: (id, patch) => req('PUT', `/recipes/${id}`, patch),
  duplicateRecipe: (id, name) => req('POST', `/recipes/${id}/duplicate`, { name: name ?? null }),
  deleteRecipe: (id) => req('DELETE', `/recipes/${id}`),

  // render
  render: (payload) => req('POST', '/render', payload),

  // datasets
  listDatasets: () => req('GET', '/datasets').then((d) => d.datasets),
  getDataset: (id) => req('GET', `/datasets/${id}`),
  createDataset: (payload) => req('POST', '/datasets', payload),
  renameDataset: (id, name) => req('PATCH', `/datasets/${id}`, { name }),
  buildDataset: (id, opts = {}) => req('POST', `/datasets/${id}/build`, opts),
  buildStatus: (id) => req('GET', `/datasets/${id}/build`),
  itemLabels: (id, i) => req('GET', `/datasets/${id}/items/${i}/labels.json`),
  itemSpec: (id, i) => req('GET', `/datasets/${id}/specs/${i}`),
  freeArtifacts: (id) => req('DELETE', `/datasets/${id}/artifacts`),
  deleteDataset: (id) => req('DELETE', `/datasets/${id}`),

  // assets
  fonts: () => req('GET', '/fonts').then((d) => d.fonts),
  photos: () => req('GET', '/backgrounds/photos').then((d) => d.files),

  // urls the browser fetches directly (img src / downloads)
  imageUrl: (id, i) => `/datasets/${id}/items/${i}/image.png`,
  maskUrl: (id, i) => `/datasets/${id}/items/${i}/mask.png`,
  archiveUrl: (id) => `/datasets/${id}/archive.zip`,
};
