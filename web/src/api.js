const BASE = '';

export async function fetchDigests(type = null) {
  const params = type ? `?type=${type}` : '';
  const res = await fetch(`${BASE}/api/digests${params}`);
  if (!res.ok) throw new Error(`Failed to fetch digests: ${res.status}`);
  return res.json();
}

export async function fetchDigest(id) {
  const res = await fetch(`${BASE}/api/digests/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch digest: ${res.status}`);
  return res.json();
}

export async function fetchItems({ source, minScore, since, limit, offset } = {}) {
  const params = new URLSearchParams();
  if (source) params.set('source', source);
  if (minScore) params.set('min_score', minScore);
  if (since) params.set('since', since);
  if (limit) params.set('limit', limit);
  if (offset) params.set('offset', offset);
  const res = await fetch(`${BASE}/api/items?${params}`);
  if (!res.ok) throw new Error(`Failed to fetch items: ${res.status}`);
  return res.json();
}

export async function fetchStats() {
  const res = await fetch(`${BASE}/api/stats`);
  if (!res.ok) throw new Error(`Failed to fetch stats: ${res.status}`);
  return res.json();
}

export async function fetchOpportunities({ minConfidence, buyer, marketType, since, limit, offset } = {}) {
  const params = new URLSearchParams();
  if (minConfidence) params.set('min_confidence', minConfidence);
  if (buyer) params.set('buyer', buyer);
  if (marketType) params.set('market_type', marketType);
  if (since) params.set('since', since);
  if (limit) params.set('limit', limit);
  if (offset) params.set('offset', offset);
  const res = await fetch(`${BASE}/api/opportunities?${params}`);
  if (!res.ok) throw new Error(`Failed to fetch opportunities: ${res.status}`);
  return res.json();
}

export async function fetchOpportunity(id) {
  const res = await fetch(`${BASE}/api/opportunities/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Failed to fetch opportunity: ${res.status}`);
  return res.json();
}

export async function fetchOpportunityTrends() {
  const res = await fetch(`${BASE}/api/opportunities/trends`);
  if (!res.ok) throw new Error(`Failed to fetch trends: ${res.status}`);
  return res.json();
}
