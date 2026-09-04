const API = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? '' : 'http://127.0.0.1:8000');

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export const api = {
  async strategies() {
    const data = await request('/api/strategies');
    return data.strategies || [];
  },
  async opportunities({ server, sort, capital, risk, strategy, limit = 12, itemId = '' }) {
    const q = new URLSearchParams({ server, sort, limit: String(limit) });
    if (capital !== '') q.set('capital', capital);
    if (risk) q.set('risk', risk);
    if (strategy) q.set('strategy', strategy);
    if (itemId) q.set('item_id', itemId);
    const data = await request(`/api/opportunities?${q}`);
    return data.opportunities || [];
  },
  async serverNames(servers) {
    const entries = await Promise.all(servers.map(async id => {
      try {
        const data = await request(`/api/sources?server=${id}`);
        return [id, data.server_name || id];
      } catch {
        return [id, id];
      }
    }));
    return Object.fromEntries(entries);
  },
  async items({ query = '', tier = '', category = '', enchantment = '', limit = 30 } = {}) {
    const q = new URLSearchParams({ limit: String(limit) });
    if (query) q.set('query', query);
    if (tier !== '') q.set('tier', tier);
    if (category) q.set('category', category);
    if (enchantment !== '') q.set('enchantment', enchantment);
    return request(`/api/items?${q}`);
  },
  async item(itemId) {
    return request(`/api/items/${encodeURIComponent(itemId)}`);
  },
  async itemMarket({ itemId, server, quality = 1 }) {
    return request(`/api/items/${encodeURIComponent(itemId)}/market?server=${encodeURIComponent(server)}&quality=${quality}`);
  },
  async itemHistory({ itemId, server, quality = 1, city = '', range = '7d' }) {
    const q = new URLSearchParams({ server, quality: String(quality) });
    if (city) q.set('city', city);
    const days = { '1d': 1, '7d': 7, '30d': 30, '90d': 90 }[range] || 7;
    const end = new Date();
    const start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000);
    q.set('start', start.toISOString());
    q.set('end', end.toISOString());
    return request(`/api/items/${encodeURIComponent(itemId)}/history?${q}`);
  },
  async itemOpportunities({ itemId, server, limit = 20 }) {
    return request(`/api/items/${encodeURIComponent(itemId)}/opportunities?server=${encodeURIComponent(server)}&limit=${limit}`);
  },
  async market({ itemId, city, quality, server }) {
    const q = new URLSearchParams({ item_id: itemId, city, quality, server });
    const spreadQuery = new URLSearchParams({ item_id: itemId, quality, server, range: '24h' });
    const [currentResponse, analysisResponse, historyResponse, spreadResponse] = await Promise.all([
      fetch(`${API}/api/market/prices?${q}`),
      fetch(`${API}/api/market/analysis?${q}&range=24h`),
      fetch(`${API}/api/market/history?${q}`),
      fetch(`${API}/api/market/spread?${spreadQuery}`),
    ]);
    if (!currentResponse.ok || !analysisResponse.ok || !historyResponse.ok) {
      throw new Error('시장 API 요청에 실패했습니다.');
    }
    return {
      current: (await currentResponse.json())[0],
      analysis: await analysisResponse.json(),
      history: await historyResponse.json(),
      spread: spreadResponse.ok ? await spreadResponse.json() : null,
    };
  },
  async systemStatus({ server }) {
    const [collector, sources, liquidity] = await Promise.allSettled([
      request('/api/collector/status'),
      request(`/api/sources?server=${encodeURIComponent(server)}`),
      request(`/api/liquidity/status?server=${encodeURIComponent(server)}`),
    ]);

    return {
      backend: {
        status: [collector, sources, liquidity].some(result => result.status === 'fulfilled') ? 'ONLINE' : 'UNKNOWN',
      },
      collector: collector.status === 'fulfilled' ? collector.value : null,
      sources: sources.status === 'fulfilled' ? sources.value : null,
      liquidity: liquidity.status === 'fulfilled' ? liquidity.value : null,
    };
  },
};

export { API };
